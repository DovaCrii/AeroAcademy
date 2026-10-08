from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class MilestoneCheck(TimeStampedModel):
    """Misión marcada por una persona. El avance se calcula, no se guarda (MODELO_DATOS)."""

    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="milestone_checks"
    )
    milestone = models.ForeignKey(
        "paths.Milestone", on_delete=models.CASCADE, related_name="checks"
    )
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "misión marcada"
        verbose_name_plural = "misiones marcadas"
        constraints = [
            models.UniqueConstraint(fields=["person", "milestone"], name="uniq_person_milestone")
        ]

    def __str__(self):
        return f"{self.person} · {self.milestone.key}"


class QuizAnswer(TimeStampedModel):
    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="quiz_answers"
    )
    question = models.ForeignKey(
        "paths.QuizQuestion", on_delete=models.CASCADE, related_name="answers"
    )
    selected_index = models.PositiveSmallIntegerField("opción elegida")
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "respuesta de quiz"
        verbose_name_plural = "respuestas de quiz"
        constraints = [
            models.UniqueConstraint(fields=["person", "question"], name="uniq_person_question")
        ]

    def __str__(self):
        return f"{self.person} · {self.question.key}"

    @property
    def is_correct(self):
        return self.selected_index == self.question.answer_index


class PathGoal(TimeStampedModel):
    """Meta de certificación de una persona en una ruta."""

    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="path_goals"
    )
    path = models.ForeignKey("paths.LearningPath", on_delete=models.CASCADE, related_name="goals")
    certification_goal = models.CharField("meta de certificación", max_length=200, blank=True)

    class Meta:
        verbose_name = "meta de certificación"
        verbose_name_plural = "metas de certificación"
        constraints = [
            models.UniqueConstraint(fields=["person", "path"], name="uniq_person_path_goal")
        ]

    def __str__(self):
        return f"{self.person} · {self.path.slug}: {self.certification_goal}"
