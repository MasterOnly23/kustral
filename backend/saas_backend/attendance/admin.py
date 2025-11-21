from django.contrib import admin
from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "employee",
        "status",
        "company",
        "branch",
        "created_at",
    )
    list_filter = ("company", "branch", "status", "date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    date_hierarchy = "date"
    ordering = ("-date",)
