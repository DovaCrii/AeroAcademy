"""Biblioteca de documentos (Bloque 9). Permisos, versiones y consultas."""

from django.db import transaction
from django.db.models import Prefetch, Q

from . import files
from .models import TITLE_MAX, Document, DocumentVersion

TAG_MAX, TAGS_LIMIT = 30, 10


def can_view(person, doc) -> bool:
    return not doc.is_restricted or person.is_lead or doc.owner_id == person.pk


def can_edit(person, doc) -> bool:
    return person.is_lead or doc.owner_id == person.pk


def visible(person):
    qs = Document.objects.all()
    if person.is_lead:
        return qs
    return qs.filter(Q(is_restricted=False) | Q(owner=person))


def clean_tags(raw):
    """Acepta texto separado por comas o una lista; devuelve etiquetas únicas, en minúsculas y acotadas."""
    items = raw.split(",") if isinstance(raw, str) else list(raw or [])
    out = []
    for item in items:
        tag = " ".join(str(item).split()).lower()[:TAG_MAX]
        if tag and tag not in out:
            out.append(tag)
    return out[:TAGS_LIMIT]


def listing(person, *, q="", doc_type="", discipline=None, tag=""):
    current = Prefetch(
        "versions", queryset=DocumentVersion.objects.filter(is_current=True), to_attr="current_list"
    )
    qs = visible(person).select_related("owner").prefetch_related("disciplines", current)
    if doc_type in Document.Type.values:
        qs = qs.filter(doc_type=doc_type)
    if discipline is not None:
        qs = qs.filter(disciplines=discipline)
    if tag:
        qs = qs.filter(tags__icontains=f'"{tag}"')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(tags__icontains=q))
    return qs.distinct()


def all_tags(person):
    seen = set()
    for tags in visible(person).values_list("tags", flat=True):
        seen.update(tags or [])
    return sorted(seen)


def _check_title(title):
    title = (title or "").strip()
    if not title:
        raise ValueError("Escribe un título.")
    if len(title) > TITLE_MAX:
        raise ValueError(f"El título admite hasta {TITLE_MAX} caracteres.")
    return title


@transaction.atomic
def create_document(
    owner,
    *,
    title,
    doc_type,
    description="",
    tags=(),
    disciplines=(),
    restricted=False,
    upload,
    label="",
    notes="",
):
    doc_type = doc_type if doc_type in Document.Type.values else Document.Type.OTHER
    doc = Document.objects.create(
        title=_check_title(title),
        doc_type=doc_type,
        description=(description or "").strip(),
        tags=clean_tags(tags),
        owner=owner,
        is_restricted=bool(restricted),
    )
    doc.disciplines.set(disciplines)
    upload_version(doc, owner, upload, label=label, notes=notes)
    return doc


@transaction.atomic
def update_document(
    doc, by, *, title, doc_type, description="", tags=(), disciplines=(), restricted=False
):
    if not can_edit(by, doc):
        raise PermissionError("Solo su dueño o un responsable puede editar el documento.")
    doc.title = _check_title(title)
    if doc_type in Document.Type.values:
        doc.doc_type = doc_type
    doc.description = (description or "").strip()
    doc.tags = clean_tags(tags)
    doc.is_restricted = bool(restricted)
    doc.save()
    doc.disciplines.set(disciplines)
    return doc


@transaction.atomic
def upload_version(doc, by, upload, *, label="", notes=""):
    """Sube una versión nueva: queda como la única vigente y el historial se conserva."""
    if not can_edit(by, doc):
        raise PermissionError("Solo su dueño o un responsable puede subir versiones.")
    ext, digest = files.validate_upload(upload)
    count = doc.versions.count()
    label = (label or "").strip()[:40] or f"v{count + 1}"
    if doc.versions.filter(version_label=label).exists():
        raise ValueError(f"Ya existe una versión «{label}».")
    DocumentVersion.objects.filter(document=doc, is_current=True).update(is_current=False)
    version = DocumentVersion(
        document=doc,
        version_label=label,
        file_ext=ext,
        file_size=upload.size,
        file_sha256=digest,
        notes=(notes or "").strip()[:300],
        uploaded_by=by,
        is_current=True,
    )
    version.file.save("x", upload, save=False)  # el nombre real lo genera upload_path
    try:
        version.save()
    except Exception:
        version.file.storage.delete(version.file.name)  # sin fila no se deja el archivo
        raise
    doc.save(update_fields=["updated_at"])
    return version


@transaction.atomic
def make_current(version, by):
    doc = version.document
    if not can_edit(by, doc):
        raise PermissionError("Solo su dueño o un responsable puede cambiar la versión vigente.")
    DocumentVersion.objects.filter(document=doc, is_current=True).exclude(pk=version.pk).update(
        is_current=False
    )
    version.is_current = True
    version.save(update_fields=["is_current", "updated_at"])
    return version


@transaction.atomic
def delete_document(doc, by):
    """Borra el documento y sus archivos (la señal `post_delete` retira cada archivo al confirmar)."""
    if not can_edit(by, doc):
        raise PermissionError("Solo su dueño o un responsable puede eliminar el documento.")
    doc.delete()
