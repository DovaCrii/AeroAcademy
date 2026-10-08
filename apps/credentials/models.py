from datetime import date

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

from .files import PrivateStorage, upload_path

WARNING_DAYS = getattr(settings, "CREDENTIAL_WARNING_DAYS", 60)


class Credential(TimeStampedModel):
    """Certificado o credencial de una persona, con su archivo privado y su revisión."""

    class Kind(models.TextChoices):
        COMPLETION = "completion", "Certificado de curso"
        CERTIFICATION = "certification", "Certificación oficial"
        LICENSE = "license", "Habilitación o permiso"
        INTERNAL = "internal", "Capacitación interna"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        PENDING = "pending", "En revisión"
        VERIFIED = "verified", "Verificada"
        REJECTED = "rejected", "Rechazada"

    class Visibility(models.TextChoices):
        TEAM = "team", "Visible para el equipo"
        PRIVATE = "private", "Solo yo y los responsables"

    owner = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="credentials"
    )
    title = models.CharField("título", max_length=250)
    issuer = models.CharField("emisor", max_length=150, blank=True)
    platform = models.ForeignKey(
        "catalog.Platform",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credentials",
    )
    kind = models.CharField("tipo", max_length=14, choices=Kind.choices, default=Kind.COMPLETION)
    credential_id = models.CharField("ID de la credencial", max_length=120, blank=True)
    verify_url = models.URLField("URL de verificación", max_length=500, blank=True)
    issued_on = models.DateField("fecha de emisión", null=True, blank=True)
    expires_on = models.DateField("vence el", null=True, blank=True)

    file = models.FileField(
        "archivo", storage=PrivateStorage(), upload_to=upload_path, max_length=200
    )
    file_sha256 = models.CharField(max_length=64, blank=True)
    file_kind = models.CharField(max_length=4, blank=True)

    resource = models.ForeignKey(
        "catalog.Resource",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credentials",
    )
    path = models.ForeignKey(
        "paths.LearningPath",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credentials",
    )
    skills = models.ManyToManyField("catalog.Skill", blank=True, related_name="credentials")
    # Curso libre: aún no está en el catálogo; un responsable puede promoverlo (resource queda nulo hasta entonces).
    course_name_free = models.CharField("nombre del curso", max_length=250, blank=True)
    course_url_free = models.URLField("enlace del curso", max_length=500, blank=True)
    completed_on = models.DateField("fecha de término", null=True, blank=True)

    status = models.CharField(
        "estado", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        "accounts.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_credentials",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField("comentario de la revisión", blank=True)
    visibility = models.CharField(
        "visibilidad", max_length=8, choices=Visibility.choices, default=Visibility.TEAM
    )

    class Meta:
        verbose_name = "credencial"
        verbose_name_plural = "credenciales"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} · {self.owner}"

    @property
    def display_title(self):
        return self.title or self.course_name_free

    @property
    def is_verified(self):
        return self.status == self.Status.VERIFIED

    @property
    def days_to_expiry(self):
        if not self.expires_on:
            return None
        return (self.expires_on - date.today()).days

    @property
    def is_expired(self):
        days = self.days_to_expiry
        return days is not None and days < 0

    @property
    def expires_soon(self):
        days = self.days_to_expiry
        return days is not None and 0 <= days <= WARNING_DAYS
