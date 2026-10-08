from django.db import models

from apps.core.models import TimeStampedModel


class BotUsage(TimeStampedModel):
    """Preguntas hechas a Teo por persona y día (para el límite diario)."""

    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="bot_usage"
    )
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "uso de Teo"
        verbose_name_plural = "usos de Teo"
        constraints = [models.UniqueConstraint(fields=["person", "day"], name="uniq_bot_usage_day")]


class BotLog(models.Model):
    """Solo metadatos: nunca se guarda el texto de la pregunta ni el de la respuesta (docs/BOT.md)."""

    person = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="bot_logs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=12, default="ask")  # ask | summary
    latency_ms = models.PositiveIntegerField(default=0)
    tokens = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "registro de Teo"
        verbose_name_plural = "registros de Teo"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.kind} {self.created_at:%Y-%m-%d %H:%M} {self.error or 'ok'}"


class IndexState(models.Model):
    """Cuándo se reconstruyó por última vez el índice de búsqueda (una sola fila)."""

    built_at = models.DateTimeField()
    rows = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.rows} filas a las {self.built_at:%H:%M}"
