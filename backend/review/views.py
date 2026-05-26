"""
Review write endpoints.

`POST /api/activities/<id>/approve/` body: {"note": "..."}
`POST /api/activities/<id>/reject/`  body: {"note": "..."}

Approval locks the activity (status -> approved). After that, no further
edits to the row are accepted at this layer. We enforce that with a guard
in `_apply_decision` rather than at the DB level so we can show a clear
error message to the analyst.

If the activity has any ERROR-severity flag, approve requires an explicit
non-empty `note` (the override reason). Warnings do not.
"""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ingestion.serializers import ActivitySerializer
from normalize.models import ActivityStatus, NormalizedActivity

from .models import ApprovalAction, ApprovalDecision


def _analyst(request) -> str:
    return (
        request.headers.get("X-Analyst-Email")
        or getattr(settings, "ANALYST_EMAIL", "analyst@example.com")
    )


def _has_blocking_error(activity: NormalizedActivity) -> bool:
    return activity.flags.filter(severity="error").exists()


def _apply_decision(request, activity_id: int, decision: str):
    activity = get_object_or_404(
        NormalizedActivity.objects.prefetch_related("flags"),
        pk=activity_id,
    )

    # Both APPROVED and REJECTED are terminal decisions. Once an analyst
    # has signed off either way the row is locked - to change it, ingest
    # a corrected file and let the new row carry its own decision. Soft
    # un-decide muddies the audit trail.
    if activity.status in (ActivityStatus.APPROVED, ActivityStatus.REJECTED):
        return Response(
            {"detail": f"Activity is already {activity.status} and locked. Re-ingest to change."},
            status=status.HTTP_409_CONFLICT,
        )

    note = (request.data.get("note") or "").strip()

    if decision == ApprovalDecision.APPROVE and _has_blocking_error(activity) and not note:
        return Response(
            {
                "detail": "This activity has an ERROR-severity flag. "
                "Provide a 'note' explaining the override to approve."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    ApprovalAction.objects.create(
        activity=activity,
        analyst=_analyst(request),
        decision=decision,
        note=note,
    )

    activity.status = (
        ActivityStatus.APPROVED
        if decision == ApprovalDecision.APPROVE
        else ActivityStatus.REJECTED
    )
    activity.save(update_fields=["status", "updated_at"])

    return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def approve(request, activity_id: int):
    return _apply_decision(request, activity_id, ApprovalDecision.APPROVE)


@api_view(["POST"])
def reject(request, activity_id: int):
    return _apply_decision(request, activity_id, ApprovalDecision.REJECT)
