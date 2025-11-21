from django.db import models
from django.conf import settings

from core.models import MultiTenantModel


class DailyCash(MultiTenantModel):
    """
    Representa el cierre de caja diario de una sucursal.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        CONFIRMED = "CONFIRMED", "Confirmado"

    date = models.DateField(help_text="Fecha del cierre de caja.")

    # Datos económicos básicos
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total de ventas del día (según sistema).",
    )

    cash_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Monto en efectivo declarado.",
    )
    card_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Monto total por tarjetas.",
    )
    qr_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Monto total por cobros con QR / billetera virtual.",
    )
    other_payments_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Otros medios de pago (cheques, transferencias, etc.).",
    )

    extra_incomes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Ingresos extra (no ventas, ej. devoluciones de gastos).",
    )
    extra_expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Egresos extra (pagos varios desde la caja).",
    )

    difference = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Diferencia de caja declarada (sobrante o faltante).",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    notes = models.TextField(
        blank=True,
        help_text="Observaciones del encargado sobre el cierre.",
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_cash_records",
        help_text="Usuario que confirmó el cierre.",
    )

    is_deleted = models.BooleanField(
        default=False,
        help_text="Indica si el cierre fue eliminado lógicamente."
    )


    class Meta:
        verbose_name = "Cierre de caja diario"
        verbose_name_plural = "Cierres de caja diarios"

        indexes = [
            models.Index(fields=["company", "branch", "date"]),
            models.Index(fields=["is_deleted"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "branch", "date"],
                condition=models.Q(is_deleted=False),
                name="unique_daily_cash_active_per_branch_and_date",
            )
        ]

        ordering = ["-date", "-created_at"]


    def __str__(self):
        company_name = self.company.name if self.company else "Sin empresa"
        branch_name = self.branch.name if self.branch else "Sin sucursal"
        return f"{company_name} - {branch_name} - {self.date} ({self.status})"

    @property
    def total_by_payment_methods(self):
        """
        Suma de todos los medios de pago cargados (efectivo + tarjeta + QR + otros).
        """
        return (
            self.cash_amount
            + self.card_amount
            + self.qr_amount
            + self.other_payments_amount
        )
