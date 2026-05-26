"""
Utility (electricity) portal CSV parser.

What we accept:
    - Standard CSV, UTF-8, comma-delimited.
    - Either calendar-month rows or arbitrary billing-period rows
      (start / end dates from the portal).
    - Mixed kWh / MWh in the same export - we keep the raw unit string
      and let normalize handle conversion.
    - Peak / off-peak split rows for the same meter & period.

The header set is small. Utility portal exports tend to be more stable
than SAP, but unit suffixes vary (some portals tack "(kWh)" onto the
consumption column header). We strip that and recover the unit from
the column header when the unit column is missing.
"""
from __future__ import annotations

import csv
import io
import re

from . import ParseResult


HEADER_ALIASES: dict[str, str] = {
    "meter":            "meter_id",
    "meter id":         "meter_id",
    "meter_id":         "meter_id",
    "mpan":             "meter_id",
    "mprn":             "meter_id",
    "supply point":     "meter_id",

    "site":             "site",
    "site name":        "site",
    "premise":          "site",
    "location":         "site",

    "period start":     "period_start",
    "start":            "period_start",
    "from":             "period_start",
    "billing start":    "period_start",

    "period end":       "period_end",
    "end":              "period_end",
    "to":               "period_end",
    "billing end":      "period_end",

    "consumption":      "consumption",
    "usage":            "consumption",
    "kwh":              "consumption",   # treated as both unit-hint and value column
    "mwh":              "consumption",
    "energy":           "consumption",

    "unit":             "unit",
    "uom":              "unit",

    "rate":             "rate",          # peak / off-peak / standard
    "tariff":           "rate",
    "register":         "rate",

    "amount":           "amount",
    "total":            "amount",
    "invoice amount":   "amount",

    "currency":         "currency",
    "ccy":              "currency",

    "invoice":          "invoice_number",
    "invoice number":   "invoice_number",
    "invoice_no":       "invoice_number",
    "bill number":      "invoice_number",
}

REQUIRED_KEYS = ("meter_id", "period_start", "period_end", "consumption")

_UNIT_IN_HEADER = re.compile(r"\((kwh|mwh|gwh|wh)\)", re.IGNORECASE)


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _normalize_header(raw: str) -> tuple[str | None, str | None]:
    """Return (internal_key, unit_hint_from_header_if_any)."""
    cleaned = (raw or "").strip().lower()
    unit_hint: str | None = None
    m = _UNIT_IN_HEADER.search(cleaned)
    if m:
        unit_hint = m.group(1)
        cleaned = _UNIT_IN_HEADER.sub("", cleaned).strip()
    key = HEADER_ALIASES.get(cleaned)
    # If the column literally is "kwh"/"mwh", the unit is in the header.
    if cleaned in ("kwh", "mwh", "gwh", "wh") and unit_hint is None:
        unit_hint = cleaned
    return key, unit_hint


def parse(content: bytes) -> ParseResult:
    result = ParseResult()
    text = _decode(content).replace("\r\n", "\n")
    if not text.strip():
        result.add_error("Empty file.")
        return result

    reader = csv.reader(io.StringIO(text))
    try:
        raw_headers = next(reader)
    except StopIteration:
        result.add_error("No header row found.")
        return result

    mapped: list[str | None] = []
    unit_hints: list[str | None] = []
    for h in raw_headers:
        key, hint = _normalize_header(h)
        mapped.append(key)
        unit_hints.append(hint)

    missing = [k for k in REQUIRED_KEYS if k not in mapped]
    if missing:
        result.add_error(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Headers seen: {', '.join(raw_headers)}."
        )
        return result

    # Pick the first non-None hint to fall back on when the row has no `unit` column.
    fallback_unit = next((h for h in unit_hints if h), None)

    for line_no, raw_row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in raw_row):
            continue
        if len(raw_row) != len(mapped):
            result.add_error(
                f"Line {line_no}: column count {len(raw_row)} != header count {len(mapped)}; skipped."
            )
            continue
        row: dict[str, str] = {}
        for key, cell in zip(mapped, raw_row):
            if key is None:
                continue
            row[key] = (cell or "").strip()
        if "unit" not in row and fallback_unit:
            row["unit"] = fallback_unit
        row["_source_line"] = str(line_no)
        result.rows.append(row)

    return result
