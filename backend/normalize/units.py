"""
Unit conversion table.

Every source-system unit gets mapped to a canonical unit + a multiplier.
Canonical units are the SI-ish forms we keep in the database:

    fuel / liquids   -> "L"      (litres)
    fuel / mass      -> "kg"
    energy           -> "kWh"
    distance         -> "km"

Why bake this into a flat dict and not a library like Pint?
- The unit zoo we see in real exports is small and predictable.
- Pint adds a dependency for two-line conversions.
- A dict is grep-able and reviewable in a PR.

If we ever ingest exotic units (tonnes of CO2e equivalent, MJ, BTU)
we add a row here, not a library.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Conversion:
    canonical: str
    factor: float


# Keys are normalized to lowercase, no whitespace, no dots.
_TABLE: dict[str, Conversion] = {
    # ── Liquids (fuel) ────────────────────────────────
    "l":         Conversion("L", 1.0),
    "ltr":       Conversion("L", 1.0),
    "lt":        Conversion("L", 1.0),
    "liter":     Conversion("L", 1.0),
    "litre":     Conversion("L", 1.0),
    "litres":    Conversion("L", 1.0),
    "liters":    Conversion("L", 1.0),
    "ml":        Conversion("L", 0.001),
    "gal":       Conversion("L", 3.78541),   # US gallon - SAP exports from US plants
    "galuk":     Conversion("L", 4.54609),

    # ── Mass ──────────────────────────────────────────
    "kg":        Conversion("kg", 1.0),
    "g":         Conversion("kg", 0.001),
    "t":         Conversion("kg", 1000.0),
    "to":        Conversion("kg", 1000.0),   # SAP German for "Tonne"
    "tonne":     Conversion("kg", 1000.0),
    "tonnes":    Conversion("kg", 1000.0),
    "mt":        Conversion("kg", 1000.0),

    # ── Energy ────────────────────────────────────────
    "kwh":       Conversion("kWh", 1.0),
    "mwh":       Conversion("kWh", 1000.0),
    "gwh":       Conversion("kWh", 1_000_000.0),
    "wh":        Conversion("kWh", 0.001),

    # ── Distance ──────────────────────────────────────
    "km":        Conversion("km", 1.0),
    "m":         Conversion("km", 0.001),
    "mi":        Conversion("km", 1.609344),
    "mile":      Conversion("km", 1.609344),
    "miles":     Conversion("km", 1.609344),

    # ── Count (nights, trips) ─────────────────────────
    "night":     Conversion("night", 1.0),
    "nights":    Conversion("night", 1.0),
    "trip":      Conversion("trip", 1.0),
    "trips":     Conversion("trip", 1.0),
}


def _key(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "").replace(".", "")


def convert(quantity: float, raw_unit: str) -> tuple[float, str] | None:
    """Return (canonical_quantity, canonical_unit) or None if the unit is unknown."""
    conv = _TABLE.get(_key(raw_unit))
    if conv is None:
        return None
    return quantity * conv.factor, conv.canonical


def known_units() -> list[str]:
    return sorted(_TABLE.keys())
