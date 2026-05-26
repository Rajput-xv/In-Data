"""
Ingestion + batch + activity read endpoints.

`POST /api/ingest/<source>/`   - multipart upload, returns the new batch.
`GET  /api/batches/`           - list batches, newest first.
`GET  /api/batches/<id>/`      - detail with aggregated counts.
`GET  /api/activities/`        - list activities, filter by status / source / batch.
`GET  /api/activities/<id>/`   - detail with flags + raw payload.

Write endpoints (approve/reject) live in review.views to keep
ingestion and review as separable concerns.
"""
from __future__ import annotations

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from normalize.models import NormalizedActivity

from .models import IngestionBatch, SourceType
from .serializers import (
    ActivitySerializer,
    IngestionBatchSerializer,
)
from .services import ingest


_VALID_SOURCES = {choice[0] for choice in SourceType.choices}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB - prototype guardrail, not a real limit


@api_view(["POST"])
@parser_classes([MultiPartParser])
def ingest_file(request, source: str):
    if source not in _VALID_SOURCES:
        return Response(
            {"detail": f"Unknown source '{source}'. Expected one of: {sorted(_VALID_SOURCES)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "Missing 'file' field in multipart body."}, status=400)
    if upload.size > _MAX_BYTES:
        return Response({"detail": f"File exceeds {_MAX_BYTES} bytes."}, status=413)

    content = upload.read()
    uploaded_by = (
        request.headers.get("X-Analyst-Email")
        or getattr(settings, "ANALYST_EMAIL", "analyst@example.com")
    )
    report = ingest(
        source_type=source,
        content=content,
        filename=upload.name,
        uploaded_by=uploaded_by,
    )

    return Response(
        {
            "batch": IngestionBatchSerializer(_with_counts(report.batch)).data,
            "rows_created": report.rows_created,
            "rows_failed": report.rows_failed,
        },
        status=status.HTTP_201_CREATED,
    )


def _annotate_counts(queryset):
    return queryset.annotate(
        activity_count=Count("activities"),
        flagged_count=Count("activities", filter=Q(activities__status="flagged")),
        approved_count=Count("activities", filter=Q(activities__status="approved")),
    )


def _with_counts(batch: IngestionBatch) -> IngestionBatch:
    return _annotate_counts(IngestionBatch.objects.filter(pk=batch.pk)).get()


@api_view(["GET"])
def list_batches(request):
    qs = _annotate_counts(IngestionBatch.objects.all())
    source = request.query_params.get("source")
    if source:
        qs = qs.filter(source_type=source)
    page_size = min(int(request.query_params.get("page_size", 50)), 200)
    return Response(
        {
            "results": IngestionBatchSerializer(qs[:page_size], many=True).data,
            "count": qs.count(),
        }
    )


@api_view(["GET"])
def batch_detail(request, batch_id: int):
    try:
        batch = _annotate_counts(IngestionBatch.objects.filter(pk=batch_id)).get()
    except IngestionBatch.DoesNotExist:
        return Response({"detail": "Batch not found."}, status=404)
    return Response(IngestionBatchSerializer(batch).data)


@api_view(["GET"])
def list_activities(request):
    qs = (
        NormalizedActivity.objects
        .select_related("batch", "raw_record")
        .prefetch_related("flags")
    )
    status_filter = request.query_params.get("status")
    source_filter = request.query_params.get("source")
    batch_filter = request.query_params.get("batch")
    activity_type = request.query_params.get("activity_type")
    scope_filter = request.query_params.get("scope")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if source_filter:
        qs = qs.filter(batch__source_type=source_filter)
    if batch_filter:
        qs = qs.filter(batch_id=batch_filter)
    if activity_type:
        qs = qs.filter(activity_type=activity_type)
    if scope_filter:
        qs = qs.filter(scope=scope_filter)

    page_size = min(int(request.query_params.get("page_size", 100)), 500)
    total = qs.count()
    return Response(
        {
            "results": ActivitySerializer(qs[:page_size], many=True).data,
            "count": total,
        }
    )


@api_view(["GET"])
def activity_detail(request, activity_id: int):
    try:
        activity = (
            NormalizedActivity.objects
            .select_related("batch", "raw_record")
            .prefetch_related("flags", "actions")
            .get(pk=activity_id)
        )
    except NormalizedActivity.DoesNotExist:
        return Response({"detail": "Activity not found."}, status=404)
    return Response(ActivitySerializer(activity).data)
