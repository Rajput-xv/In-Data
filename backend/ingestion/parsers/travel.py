"""
Concur-shaped travel JSON parser.

What we accept:
    - A JSON file whose top-level shape mimics Concur's Expense Report
      list response: `{"Items": [ ... ]}` where each item is an expense
      entry. We also accept a bare list at the top level for convenience.

We map only the fields we use, and ignore the rest. Concur's payload is
huge - itineraries, attendees, tax detail, location objects - and most
of it isn't load-bearing for emissions accounting. Picking a narrow
projection now keeps the data model honest.

Fields we read:
    Id                       -> source_ref       (Concur expense entry id)
    ExpenseTypeName          -> expense_type     (drives activity_type)
    TransactionDate          -> transaction_date
    TransactionAmount        -> amount
    TransactionCurrencyCode  -> currency
    VendorDescription        -> vendor
    LocationName             -> location_name
    OriginCity / OriginIataCode       -> origin
    DestinationCity / DestinationIataCode -> destination
    CheckInDate / CheckOutDate -> hotel period
    Description              -> description
"""
from __future__ import annotations

import json

from . import ParseResult


# Only entries with these ExpenseTypeName values translate to an activity.
# Anything else (Meals, Office Supplies, Conference Fees) is a no-op for
# emissions and we drop it - but we keep the raw record around in the DB
# so an analyst can spot-check what we ignored.
ACCEPTED_TYPES = {
    "Airfare":      "flight",
    "Air Travel":   "flight",
    "Flight":       "flight",
    "Hotel":        "hotel",
    "Lodging":      "hotel",
    "Car Rental":   "ground_transport",
    "Taxi":         "ground_transport",
    "Rail":         "ground_transport",
    "Train":        "ground_transport",
}


def _pick(item: dict, *keys: str) -> str:
    for k in keys:
        v = item.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def parse(content: bytes) -> ParseResult:
    result = ParseResult()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        result.add_error(f"Invalid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno}).")
        return result

    if isinstance(payload, dict):
        items = payload.get("Items") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        result.add_error("Top-level JSON must be an object with Items[] or a bare list.")
        return result

    if not isinstance(items, list):
        result.add_error("Expected `Items` to be a list.")
        return result

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            result.add_error(f"Entry {idx}: expected object, got {type(item).__name__}; skipped.")
            continue

        expense_type = _pick(item, "ExpenseTypeName", "expense_type")
        if expense_type not in ACCEPTED_TYPES:
            # Quietly skip non-travel expenses; record the reason so the
            # batch shows it was considered.
            result.add_error(
                f"Entry {idx} (id={_pick(item, 'Id', 'id')}): "
                f"expense type '{expense_type}' is not travel - skipped."
            )
            continue

        row = {
            "source_ref":       _pick(item, "Id", "id"),
            "expense_type":     expense_type,
            "activity_type":    ACCEPTED_TYPES[expense_type],
            "transaction_date": _pick(item, "TransactionDate", "transaction_date"),
            "amount":           _pick(item, "TransactionAmount", "amount"),
            "currency":         _pick(item, "TransactionCurrencyCode", "currency"),
            "vendor":           _pick(item, "VendorDescription", "vendor"),
            "location_name":    _pick(item, "LocationName", "location_name"),
            "origin":           _pick(item, "OriginIataCode", "OriginCity", "origin"),
            "destination":      _pick(item, "DestinationIataCode", "DestinationCity", "destination"),
            "check_in":         _pick(item, "CheckInDate", "check_in"),
            "check_out":        _pick(item, "CheckOutDate", "check_out"),
            "description":      _pick(item, "Description", "description"),
            "_source_line":     str(idx),
        }
        result.rows.append(row)

    return result
