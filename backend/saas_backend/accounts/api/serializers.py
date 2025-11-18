from rest_framework import serializers
from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "company",
            "company_name",
            "branch",
            "branch_name",
        ]
        read_only_fields = ["id", "role", "company", "branch"]
