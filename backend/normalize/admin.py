from django.contrib import admin

from .models import NormalizedActivity


@admin.register(NormalizedActivity)
class NormalizedActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "activity_type", "quantity", "unit", "period_start", "period_end", "status", "batch")
    list_filter = ("activity_type", "status", "batch__source_type")
    search_fields = ("source_ref", "location_code", "cost_center")
    readonly_fields = ("created_at", "updated_at", "raw_record", "batch")
