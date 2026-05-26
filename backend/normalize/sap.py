"""
SAP row normalizer.

Input shape: a dict produced by ingestion.parsers.sap.parse.
Output: NormalizedRow on success, NormalizeError otherwise.

Decisions made here:
    - Activity type is decided by keyword in material_text. We deliberately
      keep this dumb - if "diesel", "benzin", "petrol", "gasoline", or "fuel"
      appears, it's fuel. Otherwise procurement. The alternative (looking up
      material_number against a master table) would need a master table per
      client. We don't have one in onboarding, and a keyword check is
      transparent and easy to override.
    - Both period_start and period_end are set to posting_date. SAP postings
      are point-in-time, not period activity. We need a period range because
      utility and travel both have them, and a uniform shape makes overlap
      detection trivial.
    - Plant code is stored verbatim in `location_code`. The lookup join is
      a presentation concern (frontend resolves plant 1000 -> "Werk Hamburg").
      Storing the code keeps the row stable if the lookup table changes.
"""
from __future__ import annotations

from decimal import Decimal

from . import dateparse, numbers, units
from .result import NormalizedRow, NormalizeError


FUEL_KEYWORDS = ("diesel", "benzin", "petrol", "gasoline", "fuel", "kraftstoff", "heizöl", "heizoel")


def _activity_type(material_text: str) -> str:
    lower = (material_text or "").lower()
    if any(k in lower for k in FUEL_KEYWORDS):
        return "fuel"
    return "procurement"


def normalize(row: dict[str, str]) -> NormalizedRow | NormalizeError:
    src_line = row.get("_source_line", "")

    qty = numbers.parse(row.get("quantity", ""))
    if qty is None:
        return NormalizeError(f"Could not parse quantity '{row.get('quantity', '')}'.", src_line)

    posted = dateparse.parse(row.get("posting_date", ""))
    if posted is None:
        return NormalizeError(f"Could not parse posting_date '{row.get('posting_date', '')}'.", src_line)

    raw_unit = row.get("unit", "")
    converted = units.convert(float(qty), raw_unit)
    if converted is not None:
        canon_qty, canon_unit = converted
        out_qty = type(qty)(f"{canon_qty:.4f}")
        out_unit = canon_unit
    else:
        # Unknown unit - keep the source values verbatim. The validator
        # will flag UNIT_UNKNOWN; no point silently mis-shaping data.
        out_qty = qty
        out_unit = raw_unit

    amount = numbers.parse(row.get("amount", "")) if row.get("amount") else None

    return NormalizedRow(
        activity_type=_activity_type(row.get("material_text", "")),
        quantity=out_qty,
        unit=out_unit,
        period_start=posted,
        period_end=posted,
        location_code=row.get("plant_code", ""),
        cost_center=row.get("cost_center", ""),
        amount=amount,
        currency=(row.get("currency", "") or "").upper()[:3],
        source_ref=row.get("doc_number", ""),
    )
