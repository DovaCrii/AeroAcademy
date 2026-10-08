from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel

from .files import PrivateStorage, upload_path

TITLE_MAX = 200


class Document(TimeStampedModel):
    """Documento de la biblioteca del equipo (manuales, guías, plantillas, familias…), con versiones."""

    class Type(models.TextChoices):
        MANUAL = "manual", "Manual"
        GUIDE = "guide", "Guía"
        DRAWING = "drawing", "Plano"
        STANDARD = "standard", "Estándar"
        TEMPLATE = "template_rte", "Plantilla (.rte)"
        FAMILY = "family_rfa", "Familia (.rfa)"
        PROCEDURE = "procedure", "Procedimiento"
        OTHER = "other", "Otro"

    title = models.CharField("título", max_length=TITLE_MAX)
    doc_type = models.CharField("tipo", max_length=14, choices=Type.choices, default=Type.OTHER)
    disciplines = models.ManyToManyField("catalog.Discipline", blank=True, related_name="documents")
    tags = models.JSONField("etiquetas", default=list, blank=True)
    description = models.TextField("descripción", blank=True)
    owner = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="documents")
    is_restricted = models.BooleanField(
        "restringido", default=False, help_text="Solo su dueño y los responsables lo ven."
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["title", "id"]

    def __str__(self):
        return self.title

    @property
    def current(self):
        return next((v for v in self.versions.all() if v.is_current), None)


class DocumentVersion(TimeStampedModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version_label = models.CharField("versión", max_length=40)
    file = models.FileField(storage=PrivateStorage(), upload_to=upload_path, max_length=200)
    file_ext = models.CharField(max_length=6)
    file_size = models.PositiveBigIntegerField(default=0)
    file_sha256 = models.CharField(max_length=64)
    notes = models.CharField("notas de la versión", max_length=300, blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="document_versions"
    )
    is_current = models.BooleanField("vigente", default=False)

    class Meta:
        verbose_name = "versión de documento"
        verbose_name_plural = "versiones de documentos"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document"], condition=Q(is_current=True), name="one_current_version"
            )
        ]

    def __str__(self):
        return f"{self.document} · {self.version_label}"
