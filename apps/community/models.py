from django.db import models

from apps.core.models import TimeStampedModel

NOTE_MAX = 1000


class Note(TimeStampedModel):
    """Nota del equipo sobre una ruta, un capítulo o un recurso; las respuestas cuelgan de otra nota."""

    class Type(models.TextChoices):
        WORKS = "works", "Funciona"
        FAILS = "fails", "No funciona"
        TIP = "tip", "Recomendación"
        ASK = "ask", "Pregunta"
        REPLY = "reply", "Respuesta"

    author = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="notes")
    path = models.ForeignKey("paths.LearningPath", on_delete=models.CASCADE, related_name="notes")
    level = models.ForeignKey(
        "paths.Level", null=True, blank=True, on_delete=models.SET_NULL, related_name="notes"
    )
    resource = models.ForeignKey(
        "catalog.Resource", null=True, blank=True, on_delete=models.SET_NULL, related_name="notes"
    )
    type = models.CharField("tipo", max_length=6, choices=Type.choices)
    text = models.CharField("texto", max_length=NOTE_MAX)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    is_deleted = models.BooleanField("borrada", default=False)

    class Meta:
        verbose_name = "nota"
        verbose_name_plural = "notas"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["path", "level", "is_deleted"])]

    def __str__(self):
        return f"{self.get_type_display()} · {self.author}"
