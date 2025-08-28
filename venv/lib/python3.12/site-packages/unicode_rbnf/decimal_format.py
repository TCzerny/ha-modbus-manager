"""Handle decimal formatting.

See: https://unicode-org.github.io/icu-docs/apidoc/released/icu4c/classicu_1_1DecimalFormat.html
"""

from decimal import Decimal
from typing import Union


def format_decimal(value: Union[int, float, str, Decimal], pattern: str) -> str:
    """Format a number according to a simplified ICU DecimalFormat pattern."""
    # Split the pattern into integer and fractional parts
    if "." in pattern:
        integer_part, fractional_part = pattern.split(".")
    else:
        integer_part, fractional_part = pattern, ""

    # Determine grouping (e.g., thousands separator)
    grouping = "," in integer_part
    min_integer_digits = integer_part.replace(",", "").count("0")

    # Determine the number of decimal places
    min_fraction_digits = fractional_part.count("0")
    max_fraction_digits = len(fractional_part)

    # Round the number to the maximum fractional digits
    format_str = f"{{:.{max_fraction_digits}f}}"
    rounded_value = format_str.format(value)

    # Split the rounded value into integer and fractional parts
    if fractional_part:
        integer_value, fractional_value = rounded_value.split(".")
        fractional_value = fractional_value[:max_fraction_digits].rstrip("0")
    else:
        integer_value, fractional_value = rounded_value, ""

    # Apply integer padding
    if len(integer_value) < min_integer_digits:
        integer_value = integer_value.zfill(min_integer_digits)

    # Apply grouping
    if grouping:
        # pylint: disable=consider-using-f-string
        integer_value = "{:,}".format(int(integer_value))

    # Combine integer and fractional parts
    if min_fraction_digits > 0:
        fractional_value = fractional_value.ljust(min_fraction_digits, "0")
        formatted_number = f"{integer_value}.{fractional_value}"
    else:
        formatted_number = integer_value

    return formatted_number
