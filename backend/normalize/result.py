"""
Shared return shape for all normalizers.

Each source-specific normalizer returns one of these. The orchestrator
in ingestion.services then turns it into a NormalizedActivity row +
flags from the validator.

`NormalizeError` is used for rows we couldn't process at all (e.g.
unparseable date). These show up in the batch's error log but never
become activities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class NormalizedRow:
    activity_type: str
    quantity: Decimal
    unit: str
    period_start: date
    period_end: date
    location_code: str = ""
    cost_center: str = ""
    amount: Decimal | None = None
    currency: str = ""
    source_ref: str = ""
    # Non-blocking issues the normalizer noticed but doesn't itself flag -
    # the validator will pick these up via its rules.
    notes: list[str] = field(default_factory=list)


@dataclass
class NormalizeError:
    reason: str
    source_line: str = ""
