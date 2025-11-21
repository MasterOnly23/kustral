from django.contrib import admin

from .models import InternalOrder, InternalOrderItem


class InternalOrderItemInline(admin.TabularInline):
    model = InternalOrderItem
    extra = 1


@admin.register(InternalOrder)
class InternalOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "branch",
        "category",
        "priority",
        "status",
        "requested_date",
        "sent_date",
        "delivered_date",
        "created_by",
    )
    list_filter = (
        "company",
        "branch",
        "status",
        "category",
        "priority",
        "requested_date",
    )
    search_fields = (
        "id",
        "branch__name",
        "company__name",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
    )
    date_hierarchy = "requested_date"
    inlines = [InternalOrderItemInline]

    readonly_fields = (
        "requested_date",
        "in_process_date",
        "sent_date",
        "delivered_date",
        "cancelled_date",
        "created_at",
        "updated_at",
        "in_process_by",
        "sent_by",
        "delivered_by",
        "cancelled_by",
    )
