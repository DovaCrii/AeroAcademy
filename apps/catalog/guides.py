"""Guías rápidas por nivel de ruta: viven en seed/rutas/<slug>.json (clave `guide` de cada nivel), versionadas."""

import json
import re
from pathlib import Path

from django.conf import settings

_CACHE = {}
# Infografías por nivel (clave `images` del nivel en la semilla): solo SVG estáticos propios.
_IMAGE = re.compile(r"^core/img/[a-z0-9_/-]+\.svg$")


def _route_json(slug):
    file = Path(settings.BASE_DIR) / "seed" / "rutas" / f"{slug}.json"
    try:
        stamp = file.stat().st_mtime_ns
    except OSError:
        return {}
    cached = _CACHE.get(slug)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    _CACHE[slug] = (stamp, data)
    return data


def guide_for(path_slug, level_code):
    """Guía del nivel (dict) o None. Campos: title, do, commands, mistakes, essential, software."""
    for level in _route_json(path_slug).get("levels", []):
        if level.get("code") == level_code:
            guide = level.get("guide")
            return guide if isinstance(guide, dict) and guide.get("do") else None
    return None


def guide_context(path, current):
    """Contexto para pintar la guía: resuelve el curso esencial entre los recursos del nivel."""
    if not current:
        return None
    guide = guide_for(path.slug, current["level"].code)
    if not guide:
        return None
    target = guide.get("essential", "")
    link = None
    for lr in current.get("resources", []) or []:
        if lr.resource.title == target and lr.resource.url:
            link = lr.resource
            break
    return {
        "guide": guide,
        "essential": link,
        "code": current["level"].code,
        "images": images_for(path.slug, current["level"].code),
    }


def images_for(path_slug, level_code):
    """Infografías del nivel (rutas de estáticos validadas), en el orden de la semilla."""
    for level in _route_json(path_slug).get("levels", []):
        if level.get("code") == level_code:
            images = level.get("images") or []
            return [i for i in images if isinstance(i, str) and _IMAGE.match(i)][:3]
    return []
