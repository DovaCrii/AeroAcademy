from django import forms
from django.db.models import Q

from apps.catalog.models import Platform, Resource, Skill
from apps.paths.models import ExternalCourse

from . import files
from .models import Credential

FREE_COURSE = "__free__"


class _UploadMixin:
    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload:
            files.validate_upload(upload)  # lanza ValidationError con un mensaje claro
        return upload


class CredentialForm(_UploadMixin, forms.Form):
    title = forms.CharField(label="Título", max_length=250)
    issuer = forms.CharField(label="Emisor", max_length=150, required=False)
    platform = forms.ModelChoiceField(
        label="Plataforma", queryset=Platform.objects.all(), required=False
    )
    resource = forms.ModelChoiceField(
        label="Curso o examen del catálogo (opcional)",
        queryset=Resource.objects.filter(
            Q(grants_completion_certificate=True) | Q(kind=Resource.Kind.EXAM)
        ).order_by("platform__name", "title"),
        required=False,
        help_text="Si eliges uno, al verificarse marca las misiones de las rutas que ese curso completa.",
    )
    kind = forms.ChoiceField(label="Tipo", choices=Credential.Kind.choices)
    credential_id = forms.CharField(label="ID de la credencial", max_length=120, required=False)
    verify_url = forms.URLField(
        label="URL de verificación", max_length=500, required=False, assume_scheme="https"
    )
    issued_on = forms.DateField(
        label="Fecha de emisión", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    expires_on = forms.DateField(
        label="Vence el", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    skills = forms.ModelMultipleChoiceField(
        label="Habilidades", queryset=Skill.objects.all(), required=False
    )
    visibility = forms.ChoiceField(label="Visibilidad", choices=Credential.Visibility.choices)
    file = forms.FileField(label="Archivo (PDF, PNG o JPG · máx. 10 MB)", required=True)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance is not None:
            self.fields["file"].required = False
            self.fields["file"].label = "Reemplazar archivo (opcional)"
            if not self.is_bound:
                for name in (
                    "title",
                    "issuer",
                    "platform",
                    "resource",
                    "kind",
                    "credential_id",
                    "verify_url",
                    "issued_on",
                    "expires_on",
                    "visibility",
                ):
                    self.initial[name] = getattr(instance, name)
                self.initial["skills"] = list(instance.skills.values_list("pk", flat=True))

    def clean(self):
        cleaned = super().clean()
        issued, expires = cleaned.get("issued_on"), cleaned.get("expires_on")
        if issued and expires and expires < issued:
            self.add_error("expires_on", "El vencimiento no puede ser anterior a la emisión.")
        return cleaned

    def data_for_service(self):
        data = dict(self.cleaned_data)
        data.pop("file", None)
        return data


class RegisterCourseForm(_UploadMixin, forms.Form):
    """Registrar un curso de una ruta externa (ej.: Bentley Learn) con su certificado."""

    course = forms.ChoiceField(label="Curso")
    course_name_free = forms.CharField(label="Nombre del curso", max_length=250, required=False)
    course_url_free = forms.URLField(
        label="Enlace del curso (opcional)", max_length=500, required=False, assume_scheme="https"
    )
    completed_on = forms.DateField(
        label="Fecha de término", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    credential_id = forms.CharField(
        label="ID de la credencial (opcional)", max_length=120, required=False
    )
    expires_on = forms.DateField(
        label="Vence el (si corresponde)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    visibility = forms.ChoiceField(
        label="Visibilidad", choices=Credential.Visibility.choices, initial="team"
    )
    file = forms.FileField(label="Certificado (PDF, PNG o JPG · máx. 10 MB)")

    def __init__(self, *args, path, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.owner = owner
        courses = (
            ExternalCourse.objects.filter(path=path, retired=False)
            .select_related("resource", "level")
            .order_by("level__order", "order")
        )
        self.courses = {c.key: c for c in courses}
        choices = [(c.key, c.resource.title) for c in courses]
        if path.allow_free_courses:
            choices.append((FREE_COURSE, "Otro curso que no está en la lista…"))
        self.fields["course"].choices = choices

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("course") == FREE_COURSE
            and not (cleaned.get("course_name_free") or "").strip()
        ):
            self.add_error("course_name_free", "Escribe el nombre del curso.")
        course = self.courses.get(cleaned.get("course") or "")
        if course and self.owner is not None:
            active = Credential.objects.filter(
                owner=self.owner,
                resource=course.resource,
                status__in=[Credential.Status.PENDING, Credential.Status.VERIFIED],
            ).exists()
            if active:
                self.add_error(
                    "course",
                    "Ya registraste este curso: espera la revisión o revisa tu credencial.",
                )
        return cleaned

    def data_for_service(self):
        c = self.cleaned_data
        data = {
            "path": self.path,
            "kind": Credential.Kind.COMPLETION,
            "credential_id": c.get("credential_id", ""),
            "completed_on": c.get("completed_on"),
            "issued_on": c.get("completed_on"),
            "expires_on": c.get("expires_on"),
            "visibility": c["visibility"],
            "platform": self.path.platform,
            "issuer": self.path.platform.name if self.path.platform else "",
        }
        if c["course"] == FREE_COURSE:
            data.update(
                title=c["course_name_free"].strip(),
                course_name_free=c["course_name_free"].strip(),
                course_url_free=c.get("course_url_free", ""),
            )
        else:
            course = self.courses[c["course"]]
            data.update(
                title=course.resource.title,
                resource=course.resource,
                kind=(
                    Credential.Kind.CERTIFICATION
                    if course.reward == ExternalCourse.Reward.RELIC
                    else Credential.Kind.COMPLETION
                ),
            )
        return data
