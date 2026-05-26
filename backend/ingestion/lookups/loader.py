"""Read-only lookup helpers. JSON loaded once at import."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_LOOKUP_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _plants() -> dict[str, dict]:
    data = json.loads((_LOOKUP_DIR / "plant_codes.json").read_text(encoding="utf-8"))
    return {row["code"]: row for row in data}


@lru_cache(maxsize=1)
def _airports() -> dict[str, dict]:
    data = json.loads((_LOOKUP_DIR / "airports.json").read_text(encoding="utf-8"))
    return {row["iata"]: row for row in data}


def plant(code: str) -> dict | None:
    return _plants().get(code)


def airport(iata: str) -> dict | None:
    return _airports().get((iata or "").upper())


def all_plants() -> list[dict]:
    return list(_plants().values())


def all_airports() -> list[dict]:
    return list(_airports().values())
