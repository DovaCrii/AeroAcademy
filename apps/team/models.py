from django.db import models

from apps.core.models import TimeStampedModel


class SharedCheck(TimeStampedModel):
    """Casilla compartida del kit o del plan de implementación: la marca todo el equipo, una sola vez."""

    item = models.OneToOneField(
        "paths.SharedItem", on_delete=models.CASCADE, related_name="shared_check"
    )
    checked_by = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="shared_checks"
    )

    class Meta:
        verbose_name = "casilla compartida marcada"
        verbose_name_plural = "casillas compartidas marcadas"

    def __str__(self):
        return f"{self.item.key} ✔"
