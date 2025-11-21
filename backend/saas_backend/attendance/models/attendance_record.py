from django.db import models

from core.models import MultiTenantModel
from accounts.models import User


class AttendanceRecord(MultiTenantModel):
    """
    Registro de presentismo diario por empleado.
    Un registro por empleado + fecha + sucursal + empresa.
    """

    class Status(models.TextChoices):
        P = "P", "Presente"
        A = "A", "Ausente"
        PT = "PT", "Presente tarde"
        F = "F", "Franco"
        FC = "FC", "Franco compensatorio"
        FE = "FE", "Feriado trabajado"
        V = "V", "Vacaciones"
        AFDS = "AFDS", "Acuerdo fin de semana"
        OTRO = "OTRO", "Otro"

    employee = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        help_text="Empleado al que corresponde el registro.",
    )
    date = models.DateField(help_text="Fecha del registro de asistencia.")
    status = models.CharField(
        max_length=5,
        choices=Status.choices,
        help_text="Código de asistencia.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Comentarios u observaciones.",
    )

    class Meta:
        verbose_name = "Registro de asistencia"
        verbose_name_plural = "Registros de asistencia"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "branch", "employee", "date"],
                name="unique_attendance_per_employee_date",
            )
        ]
        ordering = ["-date", "employee__last_name", "employee__first_name"]

    def __str__(self):
        return f"{self.date} - {self.employee} - {self.status}"
