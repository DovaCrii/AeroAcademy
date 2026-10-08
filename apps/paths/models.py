from django.db import models

from apps.catalog.models import Discipline, Platform, Product, Resource, Vendor, World
from apps.core.models import TimeStampedModel


class LearningPath(TimeStampedModel):
    """Campaña: una ruta de aprendizaje de un vendor, con su mundo visual."""

    class Kind(models.TextChoices):
        STRUCTURED = "structured", "Ruta estructurada"
        EXTERNAL_TRACK = "external_track", "Ruta externa (curso + certificado)"

    slug = models.SlugField("slug", max_length=60, unique=True)
    title = models.CharField("título", max_length=200)
    program = models.CharField("programa", max_length=200, blank=True)
    platform = models.ForeignKey(
        Platform, null=True, blank=True, on_delete=models.SET_NULL, related_name="paths"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="paths")
    products = models.ManyToManyField(Product, blank=True, related_name="paths")
    disciplines = models.ManyToManyField(Discipline, blank=True, related_name="paths")
    kind = models.CharField("tipo", max_length=16, choices=Kind.choices, default=Kind.STRUCTURED)
    world = models.CharField("mundo", max_length=12, choices=World.choices, blank=True)
    description = models.TextField("descripción", blank=True)
    allow_free_courses = models.BooleanField("admite cursos libres", default=False)
    is_published = models.BooleanField("publicada", default=True)

    class Meta:
        verbose_name = "ruta"
        verbose_name_plural = "rutas"
        ordering = ["vendor__order", "title"]

    def __str__(self):
        return self.title

    @property
    def is_external(self):
        return self.kind == self.Kind.EXTERNAL_TRACK


class Level(TimeStampedModel):
    """Capítulo de una ruta."""

    class CompletionRule(models.TextChoices):
        ALL_REQUIRED = "all_required", "Todos los obligatorios"
        ANY_ONE = "any_one", "Basta uno"

    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="levels")
    code = models.CharField("código", max_length=12)
    order = models.PositiveSmallIntegerField("orden", default=0)
    short = models.CharField("nombre corto", max_length=60)
    title = models.CharField("título", max_length=250)
    estimated_hours = models.CharField("horas estimadas", max_length=60, blank=True)
    audience = models.CharField("para quién", max_length=200, blank=True)
    goal = models.TextField("meta", blank=True)
    mastery_signals = models.JSONField("señales de dominio", default=list, blank=True)
    completion_rule = models.CharField(
        max_length=14, choices=CompletionRule.choices, default=CompletionRule.ALL_REQUIRED
    )
    is_free_courses = models.BooleanField("capítulo de cursos libres", default=False)
    resources = models.ManyToManyField(
        Resource, through="LevelResource", related_name="levels", blank=True
    )

    class Meta:
        verbose_name = "capítulo"
        verbose_name_plural = "capítulos"
        ordering = ["path", "order"]
        constraints = [models.UniqueConstraint(fields=["path", "code"], name="uniq_level_code")]

    def __str__(self):
        return f"{self.path.slug} · {self.code}"


class LevelResource(TimeStampedModel):
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="level_resources")
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="level_links")
    order = models.PositiveSmallIntegerField("orden", default=0)
    note = models.TextField("nota en esta ruta", blank=True)

    class Meta:
        ordering = ["level", "order"]
        constraints = [
            models.UniqueConstraint(fields=["level", "resource"], name="uniq_level_resource")
        ]


class _KeyedItem(TimeStampedModel):
    """Base de hitos, preguntas y cursos externos: la `key` es estable y única por ruta (D7)."""

    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="+")
    key = models.CharField("clave", max_length=30)
    order = models.PositiveSmallIntegerField("orden", default=0)
    retired = models.BooleanField("retirado", default=False)

    class Meta:
        abstract = True


class Milestone(_KeyedItem):
    """Misión de un capítulo."""

    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="milestones")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="milestones")
    text = models.TextField("texto")  # admite *término* → .term
    completed_by_resource = models.ForeignKey(
        Resource,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completes_milestones",
        verbose_name="se cumple con la credencial de",
    )

    class Meta:
        verbose_name = "hito"
        verbose_name_plural = "hitos"
        ordering = ["level__order", "order"]
        constraints = [models.UniqueConstraint(fields=["path", "key"], name="uniq_milestone_key")]

    def __str__(self):
        return self.key


class QuizQuestion(_KeyedItem):
    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="quiz_questions")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="quiz")
    question = models.TextField("pregunta")
    options = models.JSONField("opciones", default=list)
    answer_index = models.PositiveSmallIntegerField("respuesta correcta")
    explanation = models.TextField("explicación", blank=True)

    class Meta:
        verbose_name = "pregunta"
        verbose_name_plural = "preguntas"
        ordering = ["level__order", "order"]
        constraints = [models.UniqueConstraint(fields=["path", "key"], name="uniq_quiz_key")]

    def __str__(self):
        return self.key


class ExternalCourse(_KeyedItem):
    """Curso de un sitio externo que entrega certificado (rutas `external_track`)."""

    class Reward(models.TextChoices):
        TROPHY = "trophy", "Trofeo"
        RELIC = "relic", "Reliquia"

    path = models.ForeignKey(
        LearningPath, on_delete=models.CASCADE, related_name="external_courses"
    )
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="external_courses")
    resource = models.ForeignKey(
        Resource, on_delete=models.PROTECT, related_name="external_courses"
    )
    reward = models.CharField("recompensa", max_length=8, choices=Reward.choices)
    is_required = models.BooleanField("obligatorio", default=True)
    contains = models.JSONField("incluye", default=list, blank=True)
    disciplines = models.ManyToManyField(Discipline, blank=True, related_name="external_courses")

    class Meta:
        verbose_name = "curso externo"
        verbose_name_plural = "cursos externos"
        ordering = ["level__order", "order"]
        constraints = [
            models.UniqueConstraint(fields=["path", "key"], name="uniq_external_course_key")
        ]

    def __str__(self):
        return self.key


class PathExtra(TimeStampedModel):
    """Secciones del prototipo que no necesitan modelo propio en el MVP."""

    class Kind(models.TextChoices):
        CAPABILITY = "capability", "Capacidad"
        GLOSSARY = "glossary", "Glosario"
        TEAM_KIT = "team_kit", "Kit del equipo"
        ROLLOUT_PHASE = "rollout_phase", "Fase del plan"
        CERTIFICATION_GOAL = "certification_goal", "Meta de certificación"
        CERTIFICATION_STEP = "certification_step", "Peldaño de certificación"
        INTRO = "intro", "Introducción de la ruta"
        FLOW = "flow", "Flujo de la portada"

    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="extras")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    order = models.PositiveSmallIntegerField(default=0)
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ["path", "kind", "order"]


class SharedItem(TimeStampedModel):
    """Casilla compartida del equipo (kit y plan de implementación)."""

    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="shared_items")
    key = models.CharField("clave", max_length=30)
    text = models.TextField("texto")
    group_title = models.CharField("grupo", max_length=200, blank=True)
    start_week = models.PositiveSmallIntegerField(null=True, blank=True)
    end_week = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["path", "key"]
        constraints = [models.UniqueConstraint(fields=["path", "key"], name="uniq_shared_item_key")]

    def __str__(self):
        return self.key
