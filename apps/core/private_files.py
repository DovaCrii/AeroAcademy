"""Archivos privados servidos por la aplicación (infografías DGAC, fotos de cursos): una sola puerta segura.

Los archivos viven FUERA del repositorio público. Un nombre solo se acepta si cumple la lista blanca (sin carpetas,
sin `..`, tipos de imagen conocidos) y el archivo resuelto queda justo dentro de la carpeta fija. Nada se sirve por
una URL estática: las vistas llaman a `file_response`, que pone nosniff, CSP con sandbox y caché privada.
"""

import re
from pathlib import Path

from django.http import FileResponse

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.(svg|png|jpg|jpeg|webp)$", re.IGNORECASE)
CONTENT_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def is_safe_name(name) -> bool:
    return isinstance(name, str) and bool(SAFE_NAME.match(name)) and ".." not in name


def safe_file(base, name):
    """Ruta del archivo `name` dentro de la carpeta `base`, o None. Nunca sale de `base`."""
    if not is_safe_name(name):
        return None
    try:
        folder = Path(base).resolve()
        path = (folder / name).resolve()
    except (OSError, ValueError):
        return None
    if path.parent != folder or not path.is_file():
        return None
    return path


def content_type(path: Path) -> str:
    return CONTENT_TYPES[path.suffix.lstrip(".").lower()]


def file_response(path: Path) -> FileResponse:
    response = FileResponse(path.open("rb"), content_type=content_type(path))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response["Cache-Control"] = "private, max-age=300"
    return response
