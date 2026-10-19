"""Archivos privados servidos por la aplicación (infografías DGAC, fotos de cursos): una sola puerta segura.

Los archivos viven FUERA del repositorio público. Un nombre solo se acepta si cumple la lista blanca (sin carpetas,
sin `..`, tipos de imagen conocidos) y el archivo resuelto queda justo dentro de la carpeta fija. Nada se sirve por
una URL estática: las vistas llaman a `file_response`, que pone nosniff, CSP con sandbox y caché privada.
"""

import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse

from apps.dgac.constants import PRIVATE_PATH_SLUGS

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


SAFE_DOC_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.pdf$", re.IGNORECASE)
PDF_MAGIC = b"%PDF-"
MATERIAL_URL_PREFIX = (
    "/cursos/material/"  # enlace interno de los recursos con `file` (ver apps/paths/course_urls.py)
)


def is_safe_document_name(name) -> bool:
    return isinstance(name, str) and bool(SAFE_DOC_NAME.match(name)) and ".." not in name


def _inside(base, name):
    try:
        folder = Path(base).resolve()
        path = (folder / name).resolve()
    except (OSError, ValueError):
        return None
    if path.parent != folder or not path.is_file():
        return None
    return path


def safe_document(base, name):
    """Ruta del PDF `name` dentro de `base`, o None. Solo `.pdf` (nunca imágenes) y nunca sale de `base`."""
    if not is_safe_document_name(name):
        return None
    return _inside(base, name)


def _is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(PDF_MAGIC)) == PDF_MAGIC
    except OSError:
        return False


def document_response(path: Path):
    """PDF como adjunto (el visor del navegador no corre bajo CSP sandbox). None si el archivo no es un PDF real."""
    if not _is_pdf(path):
        return None
    response = FileResponse(
        path.open("rb"), content_type="application/pdf", as_attachment=True, filename=path.name
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["Cache-Control"] = "private, max-age=300"
    return response


def content_type(path: Path) -> str:
    return CONTENT_TYPES[path.suffix.lstrip(".").lower()]


def file_response(path: Path) -> FileResponse:
    response = FileResponse(path.open("rb"), content_type=content_type(path))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response["Cache-Control"] = "private, max-age=300"
    return response


def private_route_slugs() -> tuple:
    """Rutas de contenido interno: la de DGAC y cada carpeta de `PRIVATE_COURSES_DIR` con su `ruta.json`.
    Nunca entran al índice de búsqueda ni al contexto que viaja al modelo externo de Nala."""
    slugs = set(PRIVATE_PATH_SLUGS)
    try:
        for child in Path(settings.PRIVATE_COURSES_DIR).iterdir():
            if (child / "ruta.json").is_file():
                slugs.add(child.name)
    except OSError:
        pass
    return tuple(sorted(slugs))
