from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin SaaS"
        ADMIN_COMPANY = "ADMIN_COMPANY", "Admin Empresa"
        BRANCH_MANAGER = "BRANCH_MANAGER", "Encargado de Sucursal"
        EMPLOYEE = "EMPLOYEE", "Empleado"

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )

    # referencias por string para evitar problemas de orden de imports
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    branch = models.ForeignKey(
        "companies.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
