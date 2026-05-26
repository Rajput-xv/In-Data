"""
Small date-parsing helper.

Sources we see in the wild produce dates in at least four formats.
We try them in order and bail out when one sticks. Anything else lands
in the validator as `PERIOD_INVALID` - the normalizer should not raise.
"""
from __future__ import annotations

from datetime import date, datetime

_FORMATS = (
    "%Y-%m-%d",       # ISO - utility portals, Concur
    "%d.%m.%Y",       # German SAP
    "%d/%m/%Y",       # UK / EU portal
    "%m/%d/%Y",       # US (Concur for US tenants)
    "%Y%m%d",         # SAP raw internal sometimes
    "%d-%m-%Y",
    "%Y/%m/%d",
)


def parse(raw: str) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    # Strip a trailing time component if present.
    if "T" in raw:
        raw = raw.split("T", 1)[0]
    elif " " in raw and len(raw) > 10:
        raw = raw.split(" ", 1)[0]
    for fmt in _FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
