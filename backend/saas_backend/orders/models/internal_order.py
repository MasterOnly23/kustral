from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import MultiTenantModel
from accounts.models import User
from companies.models import Branch


class InternalOrder(MultiTenantModel):
    """
    Pedido interno realizado por una sucursal hacia Compras.
    Soporta trazabilidad completa de estados y responsables.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        IN_PROCESS = "IN_PROCESS", "En proceso"
        SENT = "SENT", "Enviado"
        DELIVERED = "DELIVERED", "Entregado / Recibido"
        CANCELLED = "CANCELLED", "Cancelado"

    class Priority(models.TextChoices):
        LOW = "LOW", "Baja"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "Alta"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="internal_orders",
        help_text="Sucursal que realiza el pedido.",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="internal_orders_created",
        help_text="Usuario que creó el pedido.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Estado actual del pedido.",
    )

    category = models.CharField(
        max_length=100,
        help_text="Categoría general del pedido (Librería, Limpieza, etc.).",
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
        help_text="Prioridad del pedido.",
    )

    comments = models.TextField(
        blank=True,
        help_text="Comentarios generales de la sucursal sobre el pedido.",
    )

    purchasing_notes = models.TextField(
        blank=True,
        help_text="Notas internas del área de compras.",
    )

    # 🕒 Trazabilidad de estados
    requested_date = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha en que se creó el pedido.",
    )

    in_process_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que Compras tomó el pedido como 'En proceso'.",
    )
    in_process_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internal_orders_in_process",
        help_text="Usuario que marcó el pedido como 'En proceso'.",
    )

    sent_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que el pedido fue marcado como 'Enviado'.",
    )
    sent_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internal_orders_sent",
        help_text="Usuario que marcó el pedido como 'Enviado'.",
    )

    delivered_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que la sucursal marcó el pedido como 'Entregado / Recibido'.",
    )
    delivered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internal_orders_delivered",
        help_text="Usuario que marcó el pedido como 'Entregado / Recibido'.",
    )

    cancelled_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que el pedido fue cancelado.",
    )
    cancelled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internal_orders_cancelled",
        help_text="Usuario que canceló el pedido.",
    )
    is_deleted = models.BooleanField(
            default=False,
            help_text="Indica si el pedido fue eliminado lógicamente."
        )
    deleted_by = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            related_name="internal_orders_deleted",
            help_text="Usuario que marcó el pedido como eliminado.",
        )
    deleted_at = models.DateTimeField(
            null=True,
            blank=True,
            help_text="Fecha y hora en que se marcó como eliminado.",
    )

    class Meta:
        verbose_name = "Pedido interno"
        verbose_name_plural = "Pedidos internos"
        indexes = [
            models.Index(fields=["company", "branch", "status"]),
            models.Index(fields=["is_deleted"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.id} - {self.branch.name} - {self.get_status_display()}"
