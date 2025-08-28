"""Rule-based number formatting using Unicode CLDR data."""

import importlib.metadata

from .engine import FormatOptions, FormatPurpose, FormatResult, RbnfEngine

__version__ = importlib.metadata.version("unicode_rbnf")


__all__ = [
    "__version__",
    "FormatOptions",
    "FormatPurpose",
    "FormatResult",
    "RbnfEngine",
]
