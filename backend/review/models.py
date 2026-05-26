"""
Review-side models.

Flags describe *why* a row looks suspicious. They are write-once metadata
produced by the validator at ingest time. The analyst doesn't edit
flags; they decide what to do about them via an `ApprovalAction`.

An `APPROVED` action locks the activity: subsequent edits to quantity,
unit, or period are forbidden at the API layer. That lock is the
audit-handoff guarantee.
"""
from __future__ import annotations

from django.db import models


class FlagSeverity(models.TextChoices):
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class ActivityFlag(models.Model):
    activity = models.ForeignKey(
        "normalize.NormalizedActivity",
        on_delete=models.CASCADE,
        related_name="flags",
    )
    rule_code = models.CharField(max_length=32)
    severity = models.CharField(max_length=8, choices=FlagSeverity.choices)
    message = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["activity_id", "rule_code"]
        indexes = [models.Index(fields=["rule_code"])]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "rule_code"],
                name="unique_rule_per_activity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.rule_code} on activity {self.activity_id}"


class ApprovalDecision(models.TextChoices):
    APPROVE = "approve", "Approve"
    REJECT = "reject", "Reject"


class ApprovalAction(models.Model):
    activity = models.ForeignKey(
        "normalize.NormalizedActivity",
        on_delete=models.CASCADE,
        related_name="actions",
    )
    analyst = models.CharField(max_length=255)
    decision = models.CharField(max_length=8, choices=ApprovalDecision.choices)
    note = models.CharField(max_length=1000, blank=True, default="")
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at"]
        indexes = [models.Index(fields=["activity", "-decided_at"])]

    def __str__(self) -> str:
        return f"{self.decision} on activity {self.activity_id} by {self.analyst}"
