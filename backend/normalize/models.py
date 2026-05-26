"""
The unified activity row.

One table holds every kind of measurable thing - litres of diesel, kWh of
electricity, kilometres of flight. The shape is intentionally loose so
that adding a new source later doesn't reshape the table; instead you
add a new `activity_type` enum value and a new normalizer.

`raw_record` is the audit pointer. If anyone asks "where did this number
come from?" you follow that FK back to the original row.
"""
from __future__ import annotations

from django.db import models


class ActivityType(models.TextChoices):
    FUEL = "fuel", "Fuel consumption"
    PROCUREMENT = "procurement", "Procurement spend"
    ELECTRICITY = "electricity", "Electricity"
    FLIGHT = "flight", "Flight"
    HOTEL = "hotel", "Hotel night"
    GROUND_TRANSPORT = "ground_transport", "Ground transport"


class Scope(models.TextChoices):
    """GHG Protocol scope. Derived from activity_type at ingest time
    rather than computed on read, so we can index on it and the analyst
    sees what was decided rather than what the current logic would say."""
    SCOPE_1 = "1", "Scope 1 (direct)"
    SCOPE_2 = "2", "Scope 2 (purchased energy)"
    SCOPE_3 = "3", "Scope 3 (value chain)"


# Deterministic mapping. Lives next to the enum so adding an activity_type
# forces the contributor to pick a scope at the same time.
SCOPE_FOR_ACTIVITY: dict[str, str] = {
    ActivityType.FUEL:             Scope.SCOPE_1,
    ActivityType.ELECTRICITY:      Scope.SCOPE_2,
    ActivityType.PROCUREMENT:      Scope.SCOPE_3,
    ActivityType.FLIGHT:           Scope.SCOPE_3,
    ActivityType.HOTEL:            Scope.SCOPE_3,
    ActivityType.GROUND_TRANSPORT: Scope.SCOPE_3,
}


def scope_for(activity_type: str) -> str:
    return SCOPE_FOR_ACTIVITY[activity_type]


class ActivityStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    FLAGGED = "flagged", "Flagged"
    APPROVED = "approved", "Approved (locked)"
    REJECTED = "rejected", "Rejected"


class NormalizedActivity(models.Model):
    raw_record = models.OneToOneField(
        "ingestion.RawRecord",
        on_delete=models.CASCADE,
        related_name="activity",
    )
    batch = models.ForeignKey(
        "ingestion.IngestionBatch",
        on_delete=models.CASCADE,
        related_name="activities",
    )

    activity_type = models.CharField(max_length=24, choices=ActivityType.choices)
    scope = models.CharField(max_length=1, choices=Scope.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=16)
    period_start = models.DateField()
    period_end = models.DateField()

    # Optional context - not every source supplies all of these.
    location_code = models.CharField(max_length=64, blank=True, default="")
    cost_center = models.CharField(max_length=64, blank=True, default="")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, blank=True, default="")

    # `source_ref` is the source-system identifier (SAP doc number, utility
    # invoice number, Concur expense id). We rely on this for duplicate
    # detection across batches - see review.validators.DUPLICATE_LIKELY.
    source_ref = models.CharField(max_length=128, blank=True, default="")

    status = models.CharField(
        max_length=16,
        choices=ActivityStatus.choices,
        default=ActivityStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["activity_type"]),
            models.Index(fields=["scope"]),
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["source_ref"]),
        ]

    def __str__(self) -> str:
        return f"{self.activity_type} {self.quantity} {self.unit}"

    @property
    def is_locked(self) -> bool:
        return self.status == ActivityStatus.APPROVED
