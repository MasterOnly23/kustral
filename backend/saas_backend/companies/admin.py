from django.contrib import admin
from .models import Company, Branch


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "company", "created_at", "updated_at")
    list_filter = ("company",)
    search_fields = ("name", "company__name")
    ordering = ("company", "name")
