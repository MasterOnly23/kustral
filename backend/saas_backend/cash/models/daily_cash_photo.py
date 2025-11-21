from django.db import models
from .daily_cash import DailyCash


class DailyCashPhoto(models.Model):
    daily_cash = models.ForeignKey(
        DailyCash,
        on_delete=models.CASCADE,
        related_name="photos",
        help_text="Cierre de caja al que pertenece la foto."
    )
    image = models.ImageField(
        upload_to="dailycash_photos/",
        help_text="Imagen adjunta del cierre de caja."
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de cierre de caja"
        verbose_name_plural = "Fotos de cierre de caja"

    def __str__(self):
        return f"Foto #{self.id} del cierre {self.daily_cash_id}"
