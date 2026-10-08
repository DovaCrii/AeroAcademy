from django.db import models

from apps.core.models import TimeStampedModel

TITLE_MAX = 150
BODY_MAX = 20000
TEXT_MAX = 2000


class Article(TimeStampedModel):
    """Artículo de conocimiento: lección aprendida, procedimiento o pregunta frecuente."""

    class Kind(models.TextChoices):
        LESSON = "lesson", "Lección aprendida"
        PROCEDURE = "procedure", "Procedimiento"
        FAQ = "faq", "Pregunta frecuente"

    title = models.CharField("título", max_length=TITLE_MAX)
    body = models.TextField(
        "contenido", max_length=BODY_MAX
    )  # Markdown mínimo, se renderiza escapado
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.LESSON)
    disciplines = models.ManyToManyField("catalog.Discipline", blank=True, related_name="articles")
    source_thread = models.ForeignKey(
        "community.Thread",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
    )
    author = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="articles")
    is_published = models.BooleanField("publicado", default=False)

    class Meta:
        verbose_name = "artículo"
        verbose_name_plural = "artículos"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title


class Improvement(TimeStampedModel):
    """Propuesta de mejora: Idea → Plan → Ejecución → Resultado."""

    class Stage(models.TextChoices):
        IDEA = "idea", "Idea"
        PLAN = "plan", "Plan"
        EXECUTION = "execution", "Ejecución"
        RESULT = "result", "Resultado"

    title = models.CharField("título", max_length=TITLE_MAX)
    description = models.TextField("descripción", max_length=TEXT_MAX)
    proposed_by = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="improvements"
    )
    stage = models.CharField("etapa", max_length=10, choices=Stage.choices, default=Stage.IDEA)
    owner = models.ForeignKey(
        "accounts.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    outcome = models.TextField("resultado", max_length=TEXT_MAX, blank=True)

    class Meta:
        verbose_name = "mejora"
        verbose_name_plural = "mejoras"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title
