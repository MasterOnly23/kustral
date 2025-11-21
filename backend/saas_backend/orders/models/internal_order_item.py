from django.db import models

from .internal_order import InternalOrder


class InternalOrderItem(models.Model):
    """
    Ítem dentro de un pedido interno.
    """

    order = models.ForeignKey(
        InternalOrder,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Pedido al que pertenece este ítem.",
    )

    description = models.CharField(
        max_length=255,
        help_text="Descripción del producto/insumo solicitado.",
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Cantidad solicitada.",
    )

    unit = models.CharField(
        max_length=20,
        default="unid",
        help_text="Unidad de medida (unid, caja, pack, litro, etc.).",
    )

    notes = models.TextField(
        blank=True,
        help_text="Notas específicas del ítem (marca sugerida, etc.).",
    )

    class Meta:
        verbose_name = "Ítem de pedido interno"
        verbose_name_plural = "Ítems de pedido interno"

    def __str__(self):
        return f"{self.description} x {self.quantity} {self.unit}"
