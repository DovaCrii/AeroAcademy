from django.db import models

from apps.core.models import TimeStampedModel


class World(models.TextChoices):
    """Mundo visual de una ruta (docs/MUNDOS.md)."""

    ARCHITECTURE = "architecture", "Arquitectura"
    CIVIL = "civil", "Civil-Estructural"
    SURVEY = "survey", "Topografía"
    MECHANICAL = "mechanical", "Mecánica"
    AERO = "aero", "Captura / RPA"


class Discipline(TimeStampedModel):
    slug = models.SlugField("slug", max_length=40, unique=True)
    name = models.CharField("nombre", max_length=80)
    icon = models.CharField("icono", max_length=40, blank=True)
    order = models.PositiveSmallIntegerField("orden", default=0)
    default_world = models.CharField("mundo por defecto", max_length=12, choices=World.choices)

    class Meta:
        verbose_name = "disciplina"
        verbose_name_plural = "disciplinas"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Vendor(TimeStampedModel):
    """Empresa de software: Autodesk, Bentley, Trimble…"""

    slug = models.SlugField("slug", max_length=40, unique=True)
    name = models.CharField("nombre", max_length=80)
    url = models.URLField("sitio", max_length=300, blank=True)
    logo = models.CharField("logo (SVG estático)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        verbose_name = "empresa de software"
        verbose_name_plural = "empresas de software"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="products")
    slug = models.SlugField("slug", max_length=60, unique=True)
    name = models.CharField("nombre", max_length=100)
    disciplines = models.ManyToManyField(Discipline, blank=True, related_name="products")
    order = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["vendor__order", "order", "name"]

    def __str__(self):
        return f"{self.vendor.name} · {self.name}"


class Platform(TimeStampedModel):
    """Dónde se aprende o se certifica (distinto del vendor: de quién es el software)."""

    class Kind(models.TextChoices):
        LEARNING = "learning", "Aprendizaje"
        CERTIFICATION_BODY = "certification_body", "Entidad certificadora"
        REGULATOR = "regulator", "Regulador"
        VENDOR = "vendor", "Interna / proveedor"

    slug = models.SlugField("slug", max_length=40, unique=True)
    name = models.CharField("nombre", max_length=120)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    vendor = models.ForeignKey(
        Vendor, null=True, blank=True, on_delete=models.SET_NULL, related_name="platforms"
    )
    url = models.URLField("sitio", max_length=300, blank=True)
    notes = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "plataforma"
        verbose_name_plural = "plataformas"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(TimeStampedModel):
    class Attribute(models.TextChoices):
        MOD = "MOD", "Modelado"
        CAP = "CAP", "Captura"
        ANA = "ANA", "Análisis"
        DOC = "DOC", "Documentación"
        NOR = "NOR", "Normativa"
        COL = "COL", "Colaboración"

    slug = models.SlugField("slug", max_length=60, unique=True)
    name = models.CharField("nombre", max_length=100)
    category = models.CharField("categoría", max_length=40, blank=True)
    attribute = models.CharField("atributo", max_length=3, choices=Attribute.choices, blank=True)

    class Meta:
        verbose_name = "habilidad"
        verbose_name_plural = "habilidades"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Resource(TimeStampedModel):
    class Kind(models.TextChoices):
        COURSE = "course", "Curso"
        MODULE = "module", "Módulo"
        TUTORIAL = "tutorial", "Tutorial"
        EXAM = "exam", "Examen"
        GUIDE = "guide", "Guía"
        ARTICLE = "article", "Artículo"
        COLLECTION = "collection", "Colección"
        LEARNING_PLAN = "learning_plan", "Plan de aprendizaje"

    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="resources")
    products = models.ManyToManyField(Product, blank=True, related_name="resources")
    disciplines = models.ManyToManyField(Discipline, blank=True, related_name="resources")
    skills = models.ManyToManyField(Skill, blank=True, related_name="resources")
    title = models.CharField("título", max_length=300)
    url = models.URLField("enlace", max_length=500, blank=True)
    kind = models.CharField("tipo", max_length=14, choices=Kind.choices, default=Kind.GUIDE)
    duration_text = models.CharField("duración", max_length=60, blank=True)
    is_official = models.BooleanField("oficial", default=False)
    is_free = models.BooleanField("gratuito", default=True)
    grants_completion_certificate = models.BooleanField("entrega certificado", default=False)
    prepares_for = models.CharField("prepara para", max_length=200, blank=True)
    tags = models.JSONField("etiquetas", default=list, blank=True)
    description = models.TextField("descripción", blank=True)
    verify_url = models.BooleanField("falta confirmar la URL exacta", default=False)
    proposed_by = models.ForeignKey(
        "accounts.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposed_resources",
    )

    class Meta:
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        ordering = ["platform__name", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "title"], name="uniq_resource_platform_title"
            )
        ]

    def __str__(self):
        return self.title
