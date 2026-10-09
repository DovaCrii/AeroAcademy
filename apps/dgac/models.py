from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class KnowledgeAttempt(TimeStampedModel):
    """Un intento de la prueba de conocimientos RPAS.

    Guarda su propia copia de lo preguntado (`answers`): enunciado, opciones, lo marcado y lo correcto. Así la
    revisión («en qué se equivocó, qué reforzar») sigue diciendo lo que pasó aunque el banco se edite después.
    """

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dgac_attempts"
    )
    taken_at = models.DateTimeField("rendida el", default=timezone.now)
    question_count = models.PositiveSmallIntegerField("preguntas")
    correct_count = models.PositiveSmallIntegerField("correctas")
    score_percent = models.DecimalField("puntaje (%)", max_digits=4, decimal_places=1)
    pass_percent = models.PositiveSmallIntegerField("mínimo para aprobar (%)")
    passed = models.BooleanField("aprobada")
    expires_on = models.DateField("vigente hasta", null=True, blank=True)
    answers = models.JSONField("copia de lo preguntado", default=list)
    credential = models.ForeignKey(
        "credentials.Credential",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dgac_attempts",
    )

    class Meta:
        verbose_name = "intento de prueba RPAS"
        verbose_name_plural = "intentos de prueba RPAS"
        ordering = ["-taken_at", "-id"]
        indexes = [models.Index(fields=["person", "-taken_at"])]

    def __str__(self):
        return f"{self.person} · {self.score_percent} %"

    @property
    def is_current(self):
        """Aprobada y dentro de su vigencia."""
        return bool(self.passed and self.expires_on and self.expires_on >= timezone.localdate())

    @property
    def code(self):
        return f"RPAS-{self.pk:05d}"
