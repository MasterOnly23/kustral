from rest_framework import serializers

from attendance.models import AttendanceRecord


class AttendanceRecordSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    employee_username = serializers.CharField(source="employee.username", read_only=True)
    employee_full_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "employee",
            "employee_username",
            "employee_full_name",
            "date",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "company_name",
            "branch_name",
            "employee_username",
            "employee_full_name",
            "created_at",
            "updated_at",
        ]

    def get_employee_full_name(self, obj):
        if obj.employee.first_name or obj.employee.last_name:
            return f"{obj.employee.first_name} {obj.employee.last_name}".strip()
        return obj.employee.username
