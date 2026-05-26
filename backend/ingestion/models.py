"""
Ingestion-side models.

`IngestionBatch` represents one upload event - the unit of work an analyst
either approves wholesale or picks through row by row.

`RawRecord` is the verbatim original payload. We never mutate it. If a
normalizer turns out to be wrong six months later, we can re-derive the
normalized table from these without re-asking the client for files.
"""
from __future__ import annotations

from django.db import models


class SourceType(models.TextChoices):
    SAP = "sap", "SAP (fuel / procurement)"
    UTILITY = "utility", "Utility (electricity)"
    TRAVEL = "travel", "Corporate travel"


class BatchStatus(models.TextChoices):
    PARSING = "parsing", "Parsing"
    READY = "ready", "Ready for review"
    FAILED = "failed", "Failed"


class IngestionBatch(models.Model):
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=BatchStatus.choices,
        default=BatchStatus.PARSING,
    )
    row_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    parse_errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.filename} ({self.uploaded_at:%Y-%m-%d})"


class RawRecord(models.Model):
    """One row from the source file, stored verbatim as JSON."""

    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.CASCADE,
        related_name="raw_records",
    )
    row_number = models.PositiveIntegerField()
    payload = models.JSONField()

    class Meta:
        ordering = ["batch_id", "row_number"]
        indexes = [models.Index(fields=["batch", "row_number"])]

    def __str__(self) -> str:
        return f"RawRecord {self.batch_id}:{self.row_number}"
