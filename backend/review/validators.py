"""
The "suspicious row" detector.

Each rule is a callable that takes a saved NormalizedActivity and returns
either None or a (rule_code, severity, message) tuple. Rules are
deliberately independent - adding a ninth rule means appending one
function to RULES, not touching the others.

Severity contract:
    "error"   -> the row cannot be approved by analyst until they explicitly
                 override (we still allow it via a note; auditing trail is in
                 ApprovalAction.note). Errors mean "this is almost certainly
                 wrong and you should reject or re-ingest".
    "warning" -> the row looks odd. Analyst should look at it, but can
                 approve without overriding.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from ingestion.lookups import airport, plant
from normalize.models import ActivityType, NormalizedActivity
from normalize.units import known_units


# Company default currency - single-tenant prototype assumption.
DEFAULT_CURRENCY = "EUR"

# Per-activity ranges of "looks plausible" magnitudes. The point of these is
# to catch unit-of-measure mistakes - a fuel row of 50000 *might* be a fleet
# total, but more often it's a sign someone reported litres as millilitres.
# These ranges are deliberately wide; we'd rather under-flag than spam analysts.
RANGES: dict[str, tuple[Decimal, Decimal]] = {
    ActivityType.FUEL:             (Decimal("0.1"),    Decimal("200000")),
    ActivityType.PROCUREMENT:      (Decimal("0.001"),  Decimal("10000000")),
    ActivityType.ELECTRICITY:      (Decimal("0.1"),    Decimal("10000000")),
    ActivityType.FLIGHT:           (Decimal("50"),     Decimal("20000")),
    ActivityType.HOTEL:            (Decimal("1"),      Decimal("60")),
    ActivityType.GROUND_TRANSPORT: (Decimal("1"),      Decimal("1000")),
}

MAX_PERIOD_DAYS = 90


def _rule_unit_unknown(a: NormalizedActivity):
    if a.unit.lower() not in {u.lower() for u in known_units()} and a.unit not in {"L", "kg", "kWh", "km", "night", "trip"}:
        return ("UNIT_UNKNOWN", "error", f"Unit '{a.unit}' is not in the conversion table.")


def _rule_unit_range(a: NormalizedActivity):
    bounds = RANGES.get(a.activity_type)
    if not bounds:
        return None
    lo, hi = bounds
    if a.quantity < lo or a.quantity > hi:
        return (
            "UNIT_RANGE",
            "warning",
            f"Quantity {a.quantity} {a.unit} sits outside the expected range [{lo}, {hi}] for {a.activity_type}.",
        )


def _rule_quantity_nonpositive(a: NormalizedActivity):
    if a.quantity <= 0:
        return ("QUANTITY_NONPOSITIVE", "error", f"Quantity {a.quantity} is zero or negative.")


def _rule_period_invalid(a: NormalizedActivity):
    if a.period_end < a.period_start:
        return ("PERIOD_INVALID", "error", f"period_end {a.period_end} is before period_start {a.period_start}.")
    days = (a.period_end - a.period_start).days
    if days > MAX_PERIOD_DAYS:
        return (
            "PERIOD_INVALID",
            "error",
            f"Period spans {days} days, exceeding the {MAX_PERIOD_DAYS}-day cap.",
        )


def _rule_period_overlap(a: NormalizedActivity):
    """Overlap against APPROVED rows of the same activity_type at the same
    location_code. Catches double-counting from re-ingesting a file."""
    if not a.location_code:
        return None
    qs = (
        NormalizedActivity.objects.filter(
            activity_type=a.activity_type,
            location_code=a.location_code,
            status="approved",
            period_start__lte=a.period_end,
            period_end__gte=a.period_start,
        )
        .exclude(pk=a.pk)
    )
    other = qs.first()
    if other:
        return (
            "PERIOD_OVERLAP",
            "warning",
            f"Overlaps approved activity #{other.id} ({other.period_start}..{other.period_end}).",
        )


def _rule_lookup_missing(a: NormalizedActivity):
    if a.activity_type in (ActivityType.FUEL, ActivityType.PROCUREMENT):
        if a.location_code and not plant(a.location_code):
            return (
                "LOOKUP_MISSING",
                "warning",
                f"Plant code '{a.location_code}' is not in the plant_codes lookup.",
            )
    if a.activity_type == ActivityType.FLIGHT and a.location_code:
        parts = a.location_code.split("->")
        missing = [p for p in parts if p and not airport(p)]
        if missing:
            return (
                "LOOKUP_MISSING",
                "warning",
                f"Airport code(s) not in lookup: {', '.join(missing)}.",
            )


def _rule_currency_mismatch(a: NormalizedActivity):
    if a.amount is None or not a.currency:
        return None
    if a.currency.upper() != DEFAULT_CURRENCY:
        return (
            "CURRENCY_MISMATCH",
            "warning",
            f"Amount is {a.currency.upper()} (company default is {DEFAULT_CURRENCY}); no FX rate applied yet.",
        )


def _rule_duplicate_likely(a: NormalizedActivity):
    if not a.source_ref:
        return None
    twin = (
        NormalizedActivity.objects
        .filter(source_ref=a.source_ref, activity_type=a.activity_type)
        .exclude(pk=a.pk)
        .first()
    )
    if twin:
        return (
            "DUPLICATE_LIKELY",
            "warning",
            f"source_ref '{a.source_ref}' already exists on activity #{twin.id} in batch #{twin.batch_id}.",
        )


RULES: list[Callable[[NormalizedActivity], tuple[str, str, str] | None]] = [
    _rule_unit_unknown,
    _rule_unit_range,
    _rule_quantity_nonpositive,
    _rule_period_invalid,
    _rule_period_overlap,
    _rule_lookup_missing,
    _rule_currency_mismatch,
    _rule_duplicate_likely,
]


def evaluate(activity: NormalizedActivity) -> list[tuple[str, str, str]]:
    """Run every rule against an activity. Returns list of (code, severity, message)."""
    found: list[tuple[str, str, str]] = []
    for rule in RULES:
        result = rule(activity)
        if result:
            found.append(result)
    return found
