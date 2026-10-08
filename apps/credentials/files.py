"""Archivos de credenciales: tipo real por firma, tamaño máximo y nombres generados (nunca los del usuario)."""

import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# firma → (tipo, extensión, Content-Type)
SIGNATURES = [
    (b"%PDF-", "pdf", "pdf", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "png", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "jpg", "image/jpeg"),
]
CONTENT_TYPES = {ext: ctype for _sig, _kind, ext, ctype in SIGNATURES}
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


class PrivateStorage(FileSystemStorage):
    """Guarda bajo MEDIA_ROOT, pero nunca entrega una URL pública: se descarga solo por una vista con permisos."""

    def url(self, name):
        raise ValueError("Los archivos de credenciales no tienen URL pública.")


def detect_type(head: bytes):
    """Tipo real según los primeros bytes: 'pdf', 'png', 'jpg' o None."""
    for signature, kind, _ext, _ctype in SIGNATURES:
        if head.startswith(signature):
            return kind
    return None


def validate_upload(upload):
    """Valida un archivo subido. Devuelve (tipo, sha256). Lanza ValidationError en español."""
    if upload.size > MAX_BYTES:
        raise ValidationError("El archivo pesa más de 10 MB.")
    if upload.size == 0:
        raise ValidationError("El archivo está vacío.")
    name = (upload.name or "").lower()
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Solo se aceptan archivos PDF, PNG o JPG.")

    upload.seek(0)
    head = upload.read(16)
    kind = detect_type(head)
    if kind is None:
        raise ValidationError("El contenido no es un PDF, PNG ni JPG válido.")
    if kind == "jpg" and extension not in {"jpg", "jpeg"}:
        raise ValidationError("La extensión no coincide con el contenido del archivo.")
    if kind in {"pdf", "png"} and extension != kind:
        raise ValidationError("La extensión no coincide con el contenido del archivo.")

    upload.seek(0)
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return kind, digest.hexdigest()


def upload_path(instance, _filename):
    """credentials/<persona>/<uuid>.<ext>: el nombre original no se usa nunca."""
    ext = getattr(instance, "_ext", None) or "bin"
    return f"credentials/{instance.owner_id}/{uuid.uuid4().hex}.{ext}"
