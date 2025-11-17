from django.contrib import admin
from .models import DailyCash


@admin.register(DailyCash)
class DailyCashAdmin(admin.ModelAdmin):
    list_display = ("company", "branch", "date", "total_sales", "status", "difference")
    list_filter = ("company", "branch", "status", "date")
    search_fields = ("company__name", "branch__name")
