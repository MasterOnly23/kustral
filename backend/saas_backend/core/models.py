from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Modelo base con fechas de creación y actualización.
    Lo vamos a usar en casi todas las tablas del sistema.
    """
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MultiTenantModel(TimeStampedModel):
    """
    Modelo base multi-empresa / multi-sucursal.
    Todas las tablas 'de negocio' deberían heredar de acá.
    """
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )
    branch = models.ForeignKey(
        "companies.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)ss",
    )

    class Meta:
        abstract = True
