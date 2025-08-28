"""Python implementation of Rule-Based Number Formatting (RBNF) engine from ICU.

Uses XML files from the CLDR: https://cldr.unicode.org
"""

import logging
import re
from abc import ABC
from bisect import bisect_left
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, IntFlag, auto
from math import ceil, floor, isinf, isnan, log, modf
from pathlib import Path
from typing import Dict, Final, Iterable, List, Optional, Set, Union
from xml.etree import ElementTree as et

DEFAULT_TOLERANCE: Final = 1e-8
SKIP_RULESETS: Final = {"lenient-parse"}

_LANG_DIR = Path(__file__).parent / "rbnf"
_LOGGER = logging.getLogger()

# Don't load these XML files
_EXCLUDED_XML_NAMES: Set[str] = {"root", "es_419", "en_001", "nb"}


class FormatOptions(IntFlag):
    """Extra options for formatting."""

    PRESERVE_SOFT_HYPENS = 1


class FormatPurpose(Enum):
    """Purpose of the number formatting."""

    UNKNOWN = auto()
    CARDINAL = auto()
    ORDINAL = auto()
    YEAR = auto()

    @staticmethod
    def from_ruleset_name(ruleset_name: str) -> "FormatPurpose":
        """Determine formatting purpose from ruleset name."""
        if not ruleset_name.startswith("spellout"):
            return FormatPurpose.UNKNOWN

        if "ordinal" in ruleset_name:
            return FormatPurpose.ORDINAL

        if "year" in ruleset_name:
            return FormatPurpose.YEAR

        if ("cardinal" in ruleset_name) or ("numbering" in ruleset_name):
            return FormatPurpose.CARDINAL

        return FormatPurpose.UNKNOWN


@dataclass
class FormatResult:
    """Result of formatting a number."""

    text: str
    """Formatted text from shortest ruleset name."""

    text_by_ruleset: Dict[str, str]
    """Formatted text for each ruleset."""


class RbnfError(Exception):
    """Base class for errors."""


class RulesetNotFoundError(RbnfError):
    """A requested ruleset was not found."""


class NoRuleForNumberError(RbnfError):
    """No matching rule could be found for a number."""


class RbnfRulePart(ABC):
    """Abstract base class for rule parts."""


@dataclass
class TextRulePart(RbnfRulePart):
    """Literal text rule part."""

    text: str
    """Literal text to insert."""


class SubType(str, Enum):
    """Type of substitution."""

    REMAINDER = "remainder"
    """Use remainder for rule value."""

    QUOTIENT = "quotient"
    """Use quotient for rule value."""


@dataclass
class SubRulePart(RbnfRulePart):
    """Substitution rule part."""

    type: SubType
    """Type of substitution."""

    is_optional: bool = False
    """True if substitution is optional."""

    text_before: str = ""
    """Text to insert before substitution."""

    text_after: str = ""
    """Text to insert after substitution."""

    ruleset_name: Optional[str] = None
    """Ruleset name to use during substitution (None for current ruleset name)."""

    format_pattern: Optional[str] = None
    """DecimalFormat pattern (e.g., #,##0.00)."""


@dataclass
class ReplaceRulePart(RbnfRulePart):
    """Replace with other ruleset (keep value)."""

    ruleset_name: str
    """Name of ruleset to use."""


class ParseState(str, Enum):
    """Set of rbnf parser."""

    TEXT = "text"
    SUB_OPTIONAL_BEFORE = "optional_before"
    SUB_OPTIONAL_AFTER = "optional_after"
    SUB_REMAINDER = "remainder"
    SUB_QUOTIENT = "quotient"
    SUB_RULESET_NAME = "sub_ruleset_name"
    REPLACE_RULESET_NAME = "replace_ruleset_name"


class RbnfSpecialRule(str, Enum):
    """Special rule types"""

    NEGATIVE_NUMBER = "negative_number"
    """The rule is a negative-number rule (-x)."""

    NOT_A_NUMBER = "not_a_number"
    """The rule for an IEEE 754 NaN (NaN)."""

    INFINITY = "infinity"
    """The rule for infinity (Inf)."""

    IMPROPER_FRACTION = "improper_fraction"
    """The rule for improper fractions (x.x)"""


@dataclass
class RbnfRule:
    """Parsed rbnf rule."""

    value: Union[int, RbnfSpecialRule]
    """Numeric lookup value for rule."""

    parts: List[RbnfRulePart] = field(default_factory=list)
    """Parts of rule in order to be processed."""

    radix: int = 10
    """Radix used when calculating divisor."""

    @staticmethod
    def parse(value_str: str, text: str, radix: int = 10) -> "Optional[RbnfRule]":
        """Parse RBNF rule for a value."""
        # Handle special rules
        if value_str == "-x":
            rule = RbnfRule(value=RbnfSpecialRule.NEGATIVE_NUMBER)
        elif value_str in ("x.x", "x,x"):
            rule = RbnfRule(value=RbnfSpecialRule.IMPROPER_FRACTION)
        elif value_str == "NaN":
            rule = RbnfRule(value=RbnfSpecialRule.NOT_A_NUMBER)
        elif value_str == "Inf":
            rule = RbnfRule(value=RbnfSpecialRule.INFINITY)
        else:
            try:
                rule = RbnfRule(value=int(value_str), radix=radix)
            except ValueError:
                _LOGGER.debug(
                    "Unrecognized special rule: value=%s, text=%s", value_str, text
                )
                return None

        state = ParseState.TEXT
        part: Optional[RbnfRulePart] = None
        is_sub_optional = False
        sub_text_before = ""

        for c in text:
            if c == ";":
                # End of rule text
                break

            if c == "'":
                # Placeholder
                continue

            if c in (">", "→"):
                # Divide the number by the rule's divisor and format the remainder
                if state in {ParseState.TEXT, ParseState.SUB_OPTIONAL_BEFORE}:
                    state = ParseState.SUB_REMAINDER
                    part = SubRulePart(
                        SubType.REMAINDER,
                        is_optional=is_sub_optional,
                        text_before=sub_text_before,
                    )
                    rule.parts.append(part)
                    sub_text_before = ""
                elif state in {ParseState.SUB_REMAINDER, ParseState.SUB_RULESET_NAME}:
                    if is_sub_optional:
                        state = ParseState.SUB_OPTIONAL_AFTER
                    else:
                        state = ParseState.TEXT
                        part = None
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif c in ("<", "←"):
                # Divide the number by the rule's divisor and format the quotient
                if state in {ParseState.TEXT, ParseState.SUB_OPTIONAL_BEFORE}:
                    state = ParseState.SUB_QUOTIENT
                    part = SubRulePart(SubType.QUOTIENT, is_optional=is_sub_optional)
                    rule.parts.append(part)
                elif state in {ParseState.SUB_QUOTIENT, ParseState.SUB_RULESET_NAME}:
                    if is_sub_optional:
                        state = ParseState.SUB_OPTIONAL_AFTER
                    else:
                        state = ParseState.TEXT
                        part = None
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif c == "%":
                # =%rule_name= replacement
                if state in {ParseState.SUB_QUOTIENT, ParseState.SUB_REMAINDER}:
                    assert isinstance(part, SubRulePart)
                    state = ParseState.SUB_RULESET_NAME
                    part.ruleset_name = ""
                elif state in {
                    ParseState.REPLACE_RULESET_NAME,
                    ParseState.SUB_RULESET_NAME,
                }:
                    pass
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif c == "[":
                # [optional] (start)
                if state == ParseState.TEXT:
                    is_sub_optional = True
                    state = ParseState.SUB_OPTIONAL_BEFORE
                    sub_text_before = ""
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif c == "]":
                # [optional] (end)
                if state == ParseState.SUB_OPTIONAL_AFTER:
                    is_sub_optional = False
                    state = ParseState.TEXT
                    part = None
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif c == "=":
                # =%rule_name= replacement
                if state == ParseState.TEXT:
                    part = ReplaceRulePart("")
                    rule.parts.append(part)
                    state = ParseState.REPLACE_RULESET_NAME
                elif state == ParseState.REPLACE_RULESET_NAME:
                    part = None
                    state = ParseState.TEXT
                else:
                    raise ValueError(f"Got {c} in {state}")
            elif state == ParseState.SUB_OPTIONAL_BEFORE:
                # [before ...]
                sub_text_before += c
            elif state == ParseState.SUB_OPTIONAL_AFTER:
                # [... after]
                assert isinstance(part, SubRulePart)
                part.text_after += c
            elif state == ParseState.SUB_RULESET_NAME:
                # %ruleset_name in << or >>
                assert isinstance(part, SubRulePart)
                assert part.ruleset_name is not None
                part.ruleset_name += c
            elif state == ParseState.REPLACE_RULESET_NAME:
                # =%ruleset_name=
                assert isinstance(part, ReplaceRulePart)
                part.ruleset_name += c
            elif state == ParseState.TEXT:
                # literal text
                if part is None:
                    part = TextRulePart("")
                    rule.parts.append(part)

                assert isinstance(part, TextRulePart)
                part.text += c
            elif c in ("#", "0", ",", "."):
                # decimal format pattern (e.g., #,##0.00)
                assert isinstance(part, SubRulePart)
                assert state in (
                    ParseState.SUB_REMAINDER,
                    ParseState.SUB_QUOTIENT,
                ), state
                if part.format_pattern is None:
                    part.format_pattern = ""

                part.format_pattern += c
            else:
                raise ValueError(f"Got {c} in {state}")

        return rule


@dataclass
class RbnfRuleSet:
    """Named collection of rbnf rules."""

    name: str
    """Name of ruleset."""

    numeric_rules: Dict[int, RbnfRule] = field(default_factory=dict)
    """Rules keyed by lookup number."""

    special_rules: Dict[RbnfSpecialRule, RbnfRule] = field(default_factory=dict)
    """Rules keyed by special rule type."""

    _sorted_numbers: Optional[List[int]] = field(default=None)
    """Sorted list of numeric_rules keys (updated on demand)."""

    def update(self) -> None:
        """Force update to sorted key list."""
        self._sorted_numbers = sorted(self.numeric_rules.keys())

    def find_rule(
        self,
        number: float,
        tolerance: float = DEFAULT_TOLERANCE,
        rulesets: Optional[Dict[str, "RbnfRuleSet"]] = None,
    ) -> Optional[RbnfRule]:
        """Look up closest rule by number."""

        # Special rules
        if number < 0:
            return self.find_special_rule(RbnfSpecialRule.NEGATIVE_NUMBER, rulesets)

        if isnan(number):
            return self.find_special_rule(RbnfSpecialRule.NOT_A_NUMBER, rulesets)

        if isinf(number):
            return self.find_special_rule(RbnfSpecialRule.INFINITY, rulesets)

        if abs(number - round(number)) > DEFAULT_TOLERANCE:
            return self.special_rules.get(RbnfSpecialRule.IMPROPER_FRACTION)

        # Numeric rules
        number_int = int(number)
        if (self._sorted_numbers is None) or (
            len(self._sorted_numbers) != len(self.numeric_rules)
        ):
            self.update()

        assert self._sorted_numbers is not None

        # Find index of place where number would be inserted
        index = bisect_left(self._sorted_numbers, number_int)
        num_rules = len(self._sorted_numbers)

        if index >= num_rules:
            # Last rule
            index = num_rules - 1
        elif index < 0:
            # First rule
            index = 0

        rule_number = self._sorted_numbers[index]
        if number_int < rule_number:
            # Not an exact match, use one rule down
            index = max(0, index - 1)
            rule_number = self._sorted_numbers[index]

        return self.numeric_rules.get(rule_number)

    def find_special_rule(
        self,
        special_rule: RbnfSpecialRule,
        rulesets: Optional[Dict[str, "RbnfRuleSet"]] = None,
    ) -> Optional[RbnfRule]:
        """Find special rule in this ruleset or in its 0-rule."""
        rule = self.special_rules.get(special_rule)
        if rule is not None:
            return rule

        if rulesets is None:
            # Can't resolve replacement rule
            return None

        # Find the default replacement rule
        zero_rule = self.numeric_rules.get(0)
        if (
            (zero_rule is not None)
            and zero_rule.parts
            and isinstance(zero_rule.parts[0], ReplaceRulePart)
        ):
            replace_part: ReplaceRulePart = zero_rule.parts[0]
            replace_rule = rulesets.get(replace_part.ruleset_name)
            if replace_rule is not None:
                # Try to resolve the special rule in the replacement
                return replace_rule.find_special_rule(special_rule, rulesets)

        return None


class RbnfEngine:
    """Formatting engine using rbnf."""

    def __init__(self, language: str) -> None:
        self.language = language

        # ruleset name -> ruleset
        self.rulesets: Dict[str, RbnfRuleSet] = {}

    @staticmethod
    def get_supported_languages() -> List[str]:
        """Return a list of supported language codes."""
        return sorted(
            [
                f.stem
                for f in _LANG_DIR.glob("*.xml")
                if f.stem not in _EXCLUDED_XML_NAMES
            ]
        )

    @staticmethod
    def for_language(language: str) -> "RbnfEngine":
        """Load XML rules for a language and construct an engine."""
        xml_path = _LANG_DIR / f"{language}.xml"
        if not xml_path.is_file():
            raise ValueError(f"{language} is not supported")

        engine = RbnfEngine(language=language)
        with open(xml_path, "r", encoding="utf-8") as xml_file:
            root = et.fromstring(xml_file.read())
            engine.load_xml(root)

        return engine

    def add_rule(
        self,
        value_str: str,
        rule_text: str,
        ruleset_name: str,
        radix: int = 10,
    ) -> Optional[RbnfRule]:
        """Manually add a rule to the engine."""
        assert ruleset_name is not None
        ruleset = self.rulesets.get(ruleset_name)
        if ruleset is None:
            ruleset = RbnfRuleSet(name=ruleset_name)
            self.rulesets[ruleset_name] = ruleset

        rule = RbnfRule.parse(value_str, rule_text, radix=radix)
        if rule is None:
            return rule

        if isinstance(rule.value, RbnfSpecialRule):
            # Special rule
            ruleset.special_rules[rule.value] = rule
        else:
            # Numeric rule
            ruleset.numeric_rules[rule.value] = rule

        return rule

    def load_xml(self, root: et.Element) -> None:
        """Load an XML file with rbnf rules."""
        lang_elem = root.find("identity/language")
        if lang_elem is None:
            raise ValueError("Missing identity/language element")

        language = lang_elem.attrib["type"]
        if (language != self.language) and (not self.language.startswith(language)):
            raise ValueError(f"Expected language {self.language}, got {language}")

        for group_elem in root.findall("rbnf//ruleset"):
            ruleset_name = group_elem.attrib["type"]
            if ruleset_name in SKIP_RULESETS:
                _LOGGER.debug("Skipping ruleset: %s", ruleset_name)
                continue

            for rule_elem in group_elem.findall("rbnfrule"):
                if not rule_elem.text:
                    continue

                value_str = rule_elem.attrib["value"]
                radix = int(re.sub(r"[^0-9]+", "", rule_elem.attrib.get("radix", "10")))

                self.add_rule(
                    value_str,
                    rule_elem.text,
                    ruleset_name,
                    radix=radix,
                )

    def format_number(
        self,
        number: Union[int, float, str, Decimal],
        purpose: Optional[FormatPurpose] = None,
        ruleset_names: Optional[List[str]] = None,
        radix: Optional[int] = None,
        tolerance: float = DEFAULT_TOLERANCE,
        options: Optional[FormatOptions] = None,
    ) -> FormatResult:
        """Format a number using loaded rulesets."""
        if purpose is None:
            purpose = FormatPurpose.CARDINAL

        if ruleset_names is None:
            # Gather all rulesets that fit the formatting purpose
            ruleset_names = [
                r
                for r in self.rulesets
                if FormatPurpose.from_ruleset_name(r) == purpose
                and ("verbose" not in r)
            ]

        if not ruleset_names:
            raise ValueError("No rulesets")

        if options is None:
            options = FormatOptions(0)

        # ruleset -> number string
        number_strs: Dict[str, str] = {}
        for ruleset_name in ruleset_names:
            try:
                number_str = "".join(
                    self.iter_format_number(
                        number,
                        ruleset_name=ruleset_name,
                        tolerance=tolerance,
                    )
                )

                if not (options & FormatOptions.PRESERVE_SOFT_HYPENS):
                    # https://en.wikipedia.org/wiki/Soft_hyphen
                    number_str = number_str.replace("\xad", "")

                number_strs[ruleset_name] = number_str
            except (NoRuleForNumberError, RulesetNotFoundError):
                pass  # skip ruleset

        if not number_strs:
            raise NoRuleForNumberError(f"No rules were successful for {number}")

        shortest_ruleset = sorted(number_strs, key=len)[0]

        return FormatResult(
            text=number_strs[shortest_ruleset], text_by_ruleset=number_strs
        )

    def iter_format_number(
        self,
        number: Union[int, float, str, Decimal],
        ruleset_name: str,
        radix: Optional[int] = None,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> Iterable[str]:
        """Format a number using loaded rulesets (generator)."""
        if isinstance(number, str):
            number = Decimal(number)

        assert ruleset_name is not None
        ruleset = self.rulesets.get(ruleset_name)
        if ruleset is None:
            raise RulesetNotFoundError(f"No ruleset: {ruleset_name}")

        rule = ruleset.find_rule(
            float(number), tolerance=tolerance, rulesets=self.rulesets
        )
        if rule is None:
            raise NoRuleForNumberError(f"No rule for {number} in {ruleset_name}")

        q: int = 0
        r: int = 0

        if isinstance(rule.value, RbnfSpecialRule):
            if rule.value == RbnfSpecialRule.NEGATIVE_NUMBER:
                r = int(-number)
            elif rule.value == RbnfSpecialRule.IMPROPER_FRACTION:
                frac_part, int_part = modf(number)
                q = int(int_part)
                r = fractional_to_int(frac_part * 10, tolerance=tolerance)
            elif rule.value in {RbnfSpecialRule.NOT_A_NUMBER, RbnfSpecialRule.INFINITY}:
                # Should just be text substitutions
                pass
            else:
                _LOGGER.warning("Unhandled special rule: %s", rule.value)
        elif rule.value > 0:
            power_below = rule.radix ** int(floor(log(rule.value, rule.radix)))
            power_above = rule.radix ** int(ceil(log(rule.value, rule.radix)))
            divisor = power_above if (number >= power_above) else power_below
            q, r = divmod(number, divisor)

        for part in rule.parts:
            if isinstance(part, TextRulePart):
                if part.text:
                    yield part.text
            elif isinstance(part, SubRulePart):
                sub_part: SubRulePart = part

                if part.type == SubType.QUOTIENT:
                    if (q == 0) and (
                        sub_part.is_optional or (part.ruleset_name is None)
                    ):
                        # Rulesets can use quotients of zero
                        continue

                    if part.text_before:
                        yield part.text_before
                    yield from self.iter_format_number(
                        q,
                        ruleset_name=part.ruleset_name or ruleset_name,
                        tolerance=tolerance,
                    )
                    if part.text_after:
                        yield part.text_after
                elif part.type == SubType.REMAINDER:
                    if (r == 0) and (
                        sub_part.is_optional or (part.ruleset_name is None)
                    ):
                        # Rulesets can use remainders of zero
                        continue

                    if part.text_before:
                        yield part.text_before
                    yield from self.iter_format_number(
                        r,
                        ruleset_name=part.ruleset_name or ruleset_name,
                        tolerance=tolerance,
                    )
                    if part.text_after:
                        yield part.text_after
            elif isinstance(part, ReplaceRulePart):
                yield from self.iter_format_number(
                    number,
                    ruleset_name=part.ruleset_name,
                    tolerance=tolerance,
                )


def fractional_to_int(frac_part: float, tolerance: float = DEFAULT_TOLERANCE) -> int:
    """Convert fractional part to int like 0.14000000000000012 -> 14"""
    frac_int = round(frac_part)

    if abs(frac_part - frac_int) > tolerance:
        return fractional_to_int(frac_part * 10, tolerance=tolerance)

    return frac_int
