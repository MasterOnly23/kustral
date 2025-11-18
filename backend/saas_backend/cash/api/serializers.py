from rest_framework import serializers
from cash.models import DailyCash


class DailyCashSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    closed_by_username = serializers.CharField(
        source="closed_by.username", read_only=True
    )
    total_by_payment_methods = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = DailyCash
        fields = [
            "id",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "date",
            "total_sales",
            "cash_amount",
            "card_amount",
            "qr_amount",
            "other_payments_amount",
            "extra_incomes",
            "extra_expenses",
            "difference",
            "status",
            "notes",
            "closed_by",
            "closed_by_username",
            "total_by_payment_methods",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "branch_name",
            "closed_by",
            "closed_by_username",
            "total_by_payment_methods",
            "created_at",
            "updated_at",
        ]
