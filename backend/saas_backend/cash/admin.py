# cash/admin.py

from django.contrib import admin
from .models import DailyCash, DailyCashPhoto

class DailyCashPhotoInline(admin.TabularInline):
    model = DailyCashPhoto
    extra = 1


@admin.register(DailyCash)
class DailyCashAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "branch",
        "date",
        "total_sales",
        "difference",
        "created_at",
        # "status",
        "is_confirmed",
        "closed_by",
        "is_deleted",
    )
    list_filter = ("company", "branch", "status", "date", "is_deleted")
    search_fields = ("company__name", "branch__name")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")


    @admin.display(boolean=True, description="Confirmado")
    def is_confirmed(self, obj):
        return obj.status == obj.Status.CONFIRMED
