"""
SAP flat-file parser.

What we accept:
    - Semicolon-delimited CSV (SAP's default when you "Save as text" from SE16N).
    - UTF-16 LE with BOM, UTF-8 with BOM, or plain UTF-8 - we sniff and decode.
    - German or English headers. We map both to a common set of internal keys.
    - European decimals (`1.234,56`) handed off as strings; conversion happens
      in normalize/sap.py so the parser layer stays decoder-only.

What we don't:
    - IDoc XML, multi-line records, Z-fields, currency conversion at posting.
    - Header sniffing beyond a fixed alias table. If a client invents a new
      column name we want the import to fail loudly, not silently miss data.

Why a header-alias map instead of "just trust column order"?
    Because SAP exports vary by user-config: someone toggles a column off,
    the positional layout shifts, and we silently misalign. Named columns
    are the only stable contract.
"""
from __future__ import annotations

import csv
import io

from . import ParseResult


# Map from any tolerated header (lowercased, trimmed) -> our internal key.
HEADER_ALIASES: dict[str, str] = {
    # Document / line identifier
    "belegnummer":      "doc_number",
    "buchungsbeleg":    "doc_number",
    "document number":  "doc_number",
    "doc number":       "doc_number",
    "doc no":           "doc_number",

    # Posting date
    "buchungsdatum":    "posting_date",
    "buch.datum":       "posting_date",
    "posting date":     "posting_date",
    "doc date":         "posting_date",

    # Plant code
    "werk":             "plant_code",
    "plant":            "plant_code",
    "plant code":       "plant_code",

    # Material number / id
    "materialnummer":   "material_number",
    "material":         "material_number",
    "material number":  "material_number",
    "matnr":            "material_number",

    # Material description
    "kurztext":         "material_text",
    "material text":    "material_text",
    "description":      "material_text",

    # Quantity
    "menge":            "quantity",
    "quantity":         "quantity",
    "qty":              "quantity",

    # Unit of measure
    "mengeneinheit":    "unit",
    "me":               "unit",   # SAP short field
    "uom":              "unit",
    "unit":             "unit",
    "unit of measure":  "unit",

    # Net amount
    "nettowert":        "amount",
    "nettobetrag":      "amount",
    "betrag":           "amount",
    "amount":           "amount",
    "net amount":       "amount",

    # Currency
    "waehrung":         "currency",
    "währung":          "currency",
    "currency":         "currency",

    # Cost center
    "kostenstelle":     "cost_center",
    "kst":              "cost_center",
    "cost center":      "cost_center",
}


# These are the fields a downstream normalizer needs to decide the row is valid.
REQUIRED_KEYS = ("doc_number", "posting_date", "plant_code", "quantity", "unit")


def _decode(content: bytes) -> str:
    """Best-effort decode. Falls through encodings SAP commonly emits."""
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort: replace bad bytes so we at least get *some* data through.
    return content.decode("utf-8", errors="replace")


def _sniff_delimiter(sample: str) -> str:
    """SAP defaults to ';'. Honour ',' if a user re-saved through Excel."""
    if sample.count(";") >= sample.count(","):
        return ";"
    return ","


def _normalize_header(raw: str) -> str | None:
    key = (raw or "").strip().lower().lstrip("﻿")
    return HEADER_ALIASES.get(key)


def parse(content: bytes) -> ParseResult:
    result = ParseResult()
    text = _decode(content).replace("\r\n", "\n")
    if not text.strip():
        result.add_error("Empty file.")
        return result

    first_line = text.split("\n", 1)[0]
    delimiter = _sniff_delimiter(first_line)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    try:
        raw_headers = next(reader)
    except StopIteration:
        result.add_error("No header row found.")
        return result

    mapped = [_normalize_header(h) for h in raw_headers]
    unknown = [raw_headers[i] for i, m in enumerate(mapped) if m is None and raw_headers[i].strip()]
    if unknown:
        result.add_error(
            f"Unknown column header(s): {', '.join(unknown)}. "
            f"Add them to sap.HEADER_ALIASES or drop them before upload."
        )

    missing_required = [k for k in REQUIRED_KEYS if k not in mapped]
    if missing_required:
        result.add_error(
            f"Missing required column(s): {', '.join(missing_required)}. "
            f"Cannot ingest without these."
        )
        return result

    for line_no, raw_row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in raw_row):
            continue
        if len(raw_row) != len(mapped):
            result.add_error(
                f"Line {line_no}: column count {len(raw_row)} != header count {len(mapped)}; skipped."
            )
            continue
        row: dict[str, str] = {}
        for header_key, cell in zip(mapped, raw_row):
            if header_key is None:
                continue
            row[header_key] = (cell or "").strip()
        row["_source_line"] = str(line_no)
        result.rows.append(row)

    return result
