from django.contrib import admin

from .models import ActivityFlag, ApprovalAction


@admin.register(ActivityFlag)
class ActivityFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "rule_code", "severity", "created_at")
    list_filter = ("severity", "rule_code")


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "decision", "analyst", "decided_at")
    list_filter = ("decision",)
    search_fields = ("analyst", "note")
