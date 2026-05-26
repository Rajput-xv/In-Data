"""DRF serializers for ingestion + the unified activity row."""
from __future__ import annotations

from rest_framework import serializers

from normalize.models import NormalizedActivity
from review.models import ActivityFlag

from .models import IngestionBatch, RawRecord


class IngestionBatchSerializer(serializers.ModelSerializer):
    activity_count = serializers.IntegerField(read_only=True)
    flagged_count = serializers.IntegerField(read_only=True)
    approved_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            "id",
            "source_type",
            "filename",
            "uploaded_at",
            "uploaded_by",
            "status",
            "row_count",
            "error_count",
            "parse_errors",
            "activity_count",
            "flagged_count",
            "approved_count",
        ]
        read_only_fields = fields


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ["id", "row_number", "payload"]


class ActivityFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityFlag
        fields = ["id", "rule_code", "severity", "message", "created_at"]


class ActivitySerializer(serializers.ModelSerializer):
    flags = ActivityFlagSerializer(many=True, read_only=True)
    raw_payload = serializers.SerializerMethodField()
    source_type = serializers.CharField(source="batch.source_type", read_only=True)

    class Meta:
        model = NormalizedActivity
        fields = [
            "id",
            "batch",
            "source_type",
            "activity_type",
            "scope",
            "quantity",
            "unit",
            "period_start",
            "period_end",
            "location_code",
            "cost_center",
            "amount",
            "currency",
            "source_ref",
            "status",
            "created_at",
            "updated_at",
            "flags",
            "raw_payload",
        ]
        read_only_fields = fields

    def get_raw_payload(self, obj: NormalizedActivity) -> dict:
        return obj.raw_record.payload if obj.raw_record_id else {}
