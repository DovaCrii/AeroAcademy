"""Archivos de la biblioteca: lista de extensiones, firma real cuando se conoce, tamaño máximo y nombres generados."""

import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

MAX_BYTES = 50 * 1024 * 1024  # 50 MB

# extensión → firmas aceptadas (None = formato sin firma fija: se confía solo en la lista de extensiones)
SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "docx": [b"PK\x03\x04"],
    "xlsx": [b"PK\x03\x04"],
    "pptx": [b"PK\x03\x04"],
    "dwg": [b"AC10"],
    "rvt": [b"\xd0\xcf\x11\xe0"],
    "rte": [b"\xd0\xcf\x11\xe0"],
    "rfa": [b"\xd0\xcf\x11\xe0"],
    "rft": [b"\xd0\xcf\x11\xe0"],
    "ifc": [b"ISO-10303"],
    "dxf": None,
    "dgn": None,
    "txt": None,
    "csv": None,
}
ALLOWED_EXTENSIONS = set(SIGNATURES)
CONTENT_TYPE = "application/octet-stream"  # siempre descarga: nada se muestra en línea


class PrivateStorage(FileSystemStorage):
    """Bajo MEDIA_ROOT, sin URL pública: se descarga solo por una vista con permisos."""

    def url(self, name):
        raise ValueError("Los documentos no tienen URL pública.")


def extension_of(name):
    name = (name or "").lower()
    return name.rsplit(".", 1)[-1] if "." in name else ""


def validate_upload(upload):
    """Devuelve (extensión, sha256). Lanza ValidationError en español."""
    if upload.size == 0:
        raise ValidationError("El archivo está vacío.")
    if upload.size > MAX_BYTES:
        raise ValidationError("El archivo pesa más de 50 MB.")
    ext = extension_of(upload.name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Tipo de archivo no permitido. Se aceptan: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS))
            + "."
        )
    signatures = SIGNATURES[ext]
    if signatures:
        upload.seek(0)
        head = upload.read(16)
        if not any(head.startswith(s) for s in signatures):
            raise ValidationError("El contenido no coincide con la extensión del archivo.")
    upload.seek(0)
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return ext, digest.hexdigest()


def upload_path(instance, _filename):
    """library/<documento>/<uuid>.<ext>: el nombre original no se usa nunca."""
    return f"library/{instance.document_id}/{uuid.uuid4().hex}.{instance.file_ext or 'bin'}"
