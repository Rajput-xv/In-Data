"""
Travel row normalizer (Concur-shaped).

Activity-type decisions:
    flight             -> quantity = great-circle distance in km between
                          OriginIataCode and DestinationIataCode if both
                          are in our airports lookup. If either is missing
                          we still create the activity with quantity = 0
                          and unit = "km" - the validator will mark
                          LOOKUP_MISSING and the analyst either supplies a
                          distance manually or rejects.
    hotel              -> quantity = nights = check_out - check_in (>= 1)
                          unit = "night"
    ground_transport   -> we don't have a distance, only a TransactionAmount.
                          quantity = 1, unit = "trip", amount carries the
                          cost. Useful for spend-based emission factors.

Why great-circle and not a routing API?
    A routing API needs an external dependency and a key, adds latency,
    and for emissions purposes great-circle within ~3% is good enough.
    Most emission-factor methodologies (DEFRA, GHG Protocol) use
    great-circle as the default for air travel.
"""
from __future__ import annotations

import math
from decimal import Decimal

from ingestion.lookups import airport

from . import dateparse, numbers
from .result import NormalizedRow, NormalizeError


_EARTH_RADIUS_KM = 6371.0088


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _flight_distance_km(origin: str, destination: str) -> Decimal | None:
    a = airport(origin)
    b = airport(destination)
    if not a or not b:
        return None
    dist = _great_circle_km(a["lat"], a["lon"], b["lat"], b["lon"])
    return Decimal(f"{dist:.2f}")


def normalize(row: dict[str, str]) -> NormalizedRow | NormalizeError:
    src_line = row.get("_source_line", "")
    activity_type = row.get("activity_type", "")

    txn_date = dateparse.parse(row.get("transaction_date", ""))

    amount = numbers.parse(row.get("amount", "")) if row.get("amount") else None
    currency = (row.get("currency", "") or "").upper()[:3]

    if activity_type == "flight":
        if txn_date is None:
            return NormalizeError(f"Flight has unparseable transaction_date '{row.get('transaction_date','')}'.", src_line)
        distance = _flight_distance_km(row.get("origin", ""), row.get("destination", ""))
        return NormalizedRow(
            activity_type="flight",
            quantity=distance if distance is not None else Decimal("0"),
            unit="km",
            period_start=txn_date,
            period_end=txn_date,
            location_code=f"{row.get('origin', '')}->{row.get('destination', '')}",
            amount=amount,
            currency=currency,
            source_ref=row.get("source_ref", ""),
            notes=(
                ["airport lookup missing - quantity defaulted to 0"]
                if distance is None
                else []
            ),
        )

    if activity_type == "hotel":
        ci = dateparse.parse(row.get("check_in", ""))
        co = dateparse.parse(row.get("check_out", ""))
        if ci is None or co is None:
            return NormalizeError(
                f"Hotel missing check-in/out: ci='{row.get('check_in','')}', co='{row.get('check_out','')}'.",
                src_line,
            )
        nights = max((co - ci).days, 1)
        return NormalizedRow(
            activity_type="hotel",
            quantity=Decimal(nights),
            unit="night",
            period_start=ci,
            period_end=co,
            location_code=row.get("location_name", ""),
            amount=amount,
            currency=currency,
            source_ref=row.get("source_ref", ""),
        )

    if activity_type == "ground_transport":
        if txn_date is None:
            return NormalizeError(f"Ground transport has unparseable transaction_date '{row.get('transaction_date','')}'.", src_line)
        return NormalizedRow(
            activity_type="ground_transport",
            quantity=Decimal("1"),
            unit="trip",
            period_start=txn_date,
            period_end=txn_date,
            location_code=row.get("location_name", ""),
            amount=amount,
            currency=currency,
            source_ref=row.get("source_ref", ""),
        )

    return NormalizeError(f"Unsupported activity_type '{activity_type}'.", src_line)
