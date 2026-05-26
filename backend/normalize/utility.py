"""
Utility (electricity) row normalizer.

Notes:
    - Unit is whatever the row says (kWh / MWh). We don't pre-convert to a
      single canonical unit here - we keep the row's reported unit and let
      the validator flag UNIT_RANGE if it looks wrong. Pre-converting would
      hide source-level oddities that the analyst needs to see.
    - `location_code` = meter id. Sites can have multiple meters; we treat
      each meter as a separate location for period-overlap purposes.
    - `cost_center` is left blank - utility exports rarely have one.
"""
from __future__ import annotations

from . import dateparse, numbers, units
from .result import NormalizedRow, NormalizeError


def normalize(row: dict[str, str]) -> NormalizedRow | NormalizeError:
    src_line = row.get("_source_line", "")

    qty = numbers.parse(row.get("consumption", ""))
    if qty is None:
        return NormalizeError(f"Could not parse consumption '{row.get('consumption', '')}'.", src_line)

    start = dateparse.parse(row.get("period_start", ""))
    end = dateparse.parse(row.get("period_end", ""))
    if start is None or end is None:
        return NormalizeError(
            f"Could not parse period dates: start='{row.get('period_start', '')}', "
            f"end='{row.get('period_end', '')}'.",
            src_line,
        )

    raw_unit = row.get("unit", "") or "kWh"
    converted = units.convert(float(qty), raw_unit)
    if converted is not None:
        canon_qty, canon_unit = converted
        out_qty = type(qty)(f"{canon_qty:.4f}")
        out_unit = canon_unit
    else:
        out_qty = qty
        out_unit = raw_unit

    amount = numbers.parse(row.get("amount", "")) if row.get("amount") else None

    return NormalizedRow(
        activity_type="electricity",
        quantity=out_qty,
        unit=out_unit,
        period_start=start,
        period_end=end,
        location_code=row.get("meter_id", ""),
        cost_center="",
        amount=amount,
        currency=(row.get("currency", "") or "").upper()[:3],
        source_ref=row.get("invoice_number", "") or f"{row.get('meter_id','')}|{row.get('period_start','')}|{row.get('rate','')}",
    )
