"""Lectura del contenido privado de JEJ (carpeta `DGAC_DATA_DIR`).

El repositorio es público: aquí solo hay código. La ruta, el banco de preguntas, el texto del resumen y las
infografías son de JEJ y se leen de disco. Si algo falta, la sección dice que no está instalado; nunca falla.
"""

import json
import re
from pathlib import Path

from django.conf import settings

from . import constants

_cache: dict = {}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.(svg|png|jpg|jpeg)$")
CONTENT_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


class DataError(Exception):
    """El archivo existe pero no es válido."""


def data_dir() -> Path:
    return Path(settings.DGAC_DATA_DIR)


def read_json(name):
    """Contenido del JSON, o None si no existe. Se vuelve a leer solo si el archivo cambió."""
    path = data_dir() / name
    try:
        stat = path.stat()
    except OSError:
        return None
    key = str(path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _cache.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataError(f"{name}: no se pudo leer ({exc})") from exc
    _cache[key] = (stamp, value)
    return value


def _safe(name, default=None):
    try:
        value = read_json(name)
    except DataError:
        return default
    return default if value is None else value


# --- banco de preguntas --------------------------------------------------------------------------------------


def _unwrapped(text):
    """Espacios colapsados, sin cambiar una sola palabra (los PDF de origen traen saltos de línea a mitad de frase)."""
    return " ".join(str(text).split())


def load_bank():
    """Preguntas del banco con los espacios colapsados. Lista vacía si no está instalado o es inválido."""
    payload = _safe(constants.FILE_BANK, {})
    out = []
    for q in payload.get("questions", []):
        try:
            out.append(
                {
                    "id": q["id"],
                    "text": _unwrapped(q["text"]),
                    "topic": _unwrapped(q.get("topic", "")),
                    "options": [
                        {"key": str(o["key"]), "text": _unwrapped(o["text"])} for o in q["options"]
                    ],
                    "answer": str(q["answer"]),
                }
            )
        except (KeyError, TypeError):
            continue
    return out


def bank_source():
    return _safe(constants.FILE_BANK, {}).get("source", {})


def bank_is_available():
    return len(load_bank()) > 0


# --- resumen de operaciones ------------------------------------------------------------------------------------


def load_overview():
    """Contenido de la página «Operaciones RPAS en JEJ», o None si no está instalado."""
    value = _safe(constants.FILE_OVERVIEW, None)
    return value if isinstance(value, dict) and value.get("sections") else None


def load_route():
    return _safe(constants.FILE_ROUTE, None)


# --- infografías ---------------------------------------------------------------------------------------------------


def image_path(name):
    """Ruta segura de una infografía de la carpeta de datos, o None. El nombre nunca sale de la carpeta."""
    if not _SAFE_NAME.match(name or ""):
        return None
    base = (data_dir() / constants.DIR_IMAGES).resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_file():
        return None
    return path


def image_type(path: Path):
    return CONTENT_TYPES[path.suffix.lstrip(".").lower()]
