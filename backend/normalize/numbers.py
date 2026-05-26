"""
Decimal-number parsing that handles both European and US conventions.

Examples this handles:
    "1.234,56"  -> Decimal("1234.56")   (EU: dot=thousands, comma=decimal)
    "1,234.56"  -> Decimal("1234.56")   (US: comma=thousands, dot=decimal)
    "1234,56"   -> Decimal("1234.56")
    "1234.56"   -> Decimal("1234.56")
    "1234"      -> Decimal("1234")
    "-0,5"      -> Decimal("-0.5")
    "1 234,56"  -> Decimal("1234.56")   (some locales use spaces)

Heuristic: if both `.` and `,` appear, whichever comes *last* is the
decimal separator and the other is a thousands grouping. If only one
appears, we look at the digits to the right of it - three digits and
no further dot/comma means it's a thousands separator, otherwise it's
a decimal.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse(raw: str) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "")
    if not s:
        return None

    negative = s.startswith("-")
    if negative:
        s = s[1:]

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        # Decimal separator is whichever appears later.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma and not has_dot:
        # Lone comma - could be thousands or decimal.
        right = s.rsplit(",", 1)[1]
        if len(right) == 3 and right.isdigit() and not _looks_like_decimal(s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif has_dot and not has_comma:
        right = s.rsplit(".", 1)[1]
        if len(right) == 3 and right.isdigit() and _appears_thousands(s):
            s = s.replace(".", "")
        # else: leave as-is (already valid decimal form)

    if negative:
        s = "-" + s

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _looks_like_decimal(s: str) -> bool:
    """True if the value almost certainly contains a decimal portion
    (e.g. '1,5' or '0,25'). Used to disambiguate lone commas."""
    head, _, tail = s.partition(",")
    if not head.isdigit() or not tail.isdigit():
        return False
    # short head, e.g. "1,5" or "12,75" - comma is the decimal
    return len(head) <= 3 and len(tail) != 3


def _appears_thousands(s: str) -> bool:
    """True if multiple dot-separated groups of 3 digits suggest thousands grouping."""
    parts = s.split(".")
    if len(parts) < 3:
        return False
    return all(p.isdigit() and len(p) == 3 for p in parts[1:])
