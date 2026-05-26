from django.contrib import admin

from .models import IngestionBatch, RawRecord


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "source_type", "filename", "status", "row_count", "error_count", "uploaded_at")
    list_filter = ("source_type", "status")
    search_fields = ("filename", "uploaded_by")


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "row_number")
    list_filter = ("batch__source_type",)
