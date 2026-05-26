"""
Ingestion orchestration.

`ingest(source_type, content, filename, uploaded_by)` is the one public
function. It does the whole parse -> normalize -> validate -> save dance
inside a single transaction so a failure can't leave half-ingested rows
that the analyst dashboard might lock by mistake.

Why synchronous and not Celery?
    Prototype scale. Concretely: SQLite plus a 500-row file finishes in
    well under a second; pushing this to a worker would add infrastructure
    nobody is asking for. If a real client lands with 100k-row monthly
    drops we move this function body behind a Celery task; the function
    signature stays the same.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from normalize.models import ActivityStatus, NormalizedActivity, scope_for
from normalize.result import NormalizedRow, NormalizeError
from review.models import ActivityFlag
from review.validators import evaluate

from .models import IngestionBatch, BatchStatus, RawRecord, SourceType
from .parsers import sap as sap_parser, utility as utility_parser, travel as travel_parser

from normalize import sap as sap_normalizer, utility as utility_normalizer, travel as travel_normalizer


_PARSERS = {
    SourceType.SAP: sap_parser,
    SourceType.UTILITY: utility_parser,
    SourceType.TRAVEL: travel_parser,
}

_NORMALIZERS = {
    SourceType.SAP: sap_normalizer,
    SourceType.UTILITY: utility_normalizer,
    SourceType.TRAVEL: travel_normalizer,
}


@dataclass
class IngestReport:
    batch: IngestionBatch
    rows_created: int
    rows_failed: int


def ingest(source_type: str, content: bytes, filename: str, uploaded_by: str) -> IngestReport:
    if source_type not in _PARSERS:
        raise ValueError(f"Unknown source_type '{source_type}'.")

    with transaction.atomic():
        batch = IngestionBatch.objects.create(
            source_type=source_type,
            filename=filename,
            uploaded_by=uploaded_by,
            status=BatchStatus.PARSING,
        )

        parser = _PARSERS[source_type]
        normalizer = _NORMALIZERS[source_type]

        parse_result = parser.parse(content)
        batch.parse_errors = list(parse_result.errors)

        rows_created = 0
        rows_failed = len(parse_result.errors)

        for row in parse_result.rows:
            row_number = int(row.get("_source_line") or 0)
            raw = RawRecord.objects.create(
                batch=batch,
                row_number=row_number,
                payload={k: v for k, v in row.items() if not k.startswith("_")},
            )

            normalized = normalizer.normalize(row)
            if isinstance(normalized, NormalizeError):
                batch.parse_errors.append(
                    f"Line {normalized.source_line or row_number}: {normalized.reason}"
                )
                rows_failed += 1
                continue

            activity = _save_activity(batch, raw, normalized)
            flags = evaluate(activity)

            if flags:
                ActivityFlag.objects.bulk_create(
                    [
                        ActivityFlag(
                            activity=activity,
                            rule_code=code,
                            severity=severity,
                            message=message,
                        )
                        for code, severity, message in flags
                    ]
                )
                activity.status = ActivityStatus.FLAGGED
                activity.save(update_fields=["status"])

            rows_created += 1

        batch.row_count = rows_created
        batch.error_count = rows_failed
        batch.status = BatchStatus.READY
        batch.save()

    return IngestReport(batch=batch, rows_created=rows_created, rows_failed=rows_failed)


def _save_activity(
    batch: IngestionBatch,
    raw: RawRecord,
    n: NormalizedRow,
) -> NormalizedActivity:
    return NormalizedActivity.objects.create(
        raw_record=raw,
        batch=batch,
        activity_type=n.activity_type,
        scope=scope_for(n.activity_type),
        quantity=n.quantity,
        unit=n.unit,
        period_start=n.period_start,
        period_end=n.period_end,
        location_code=n.location_code,
        cost_center=n.cost_center,
        amount=n.amount,
        currency=n.currency,
        source_ref=n.source_ref,
    )
