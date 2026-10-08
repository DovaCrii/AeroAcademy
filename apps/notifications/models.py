from django.db import models

from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """Aviso dentro de la app para una persona. `key` evita repetir el mismo aviso (idempotencia)."""

    recipient = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField("tipo", max_length=30)
    title = models.CharField("título", max_length=200)
    body = models.CharField("detalle", max_length=300, blank=True)
    url = models.CharField("enlace", max_length=300, blank=True)
    key = models.CharField(max_length=120, blank=True)
    read_at = models.DateTimeField("leído", null=True, blank=True)

    class Meta:
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "key"],
                condition=~models.Q(key=""),
                name="uniq_notification_key",
            )
        ]

    def __str__(self):
        return f"{self.recipient}: {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None


class Announcement(TimeStampedModel):
    """Anuncio del moderador: banda en la portada y aviso para todas las personas."""

    author = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="announcements"
    )
    title = models.CharField("título", max_length=120)
    body = models.CharField("texto", max_length=500)
    expires_on = models.DateField("vence el")

    class Meta:
        verbose_name = "anuncio"
        verbose_name_plural = "anuncios"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
