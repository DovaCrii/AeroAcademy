import re
from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.core import markdown as md_lite

register = template.Library()

_TERM = re.compile(r"\*([^*\n]+)\*")


@register.filter
def terms(value):
    """Escapa el texto y convierte `*término*` en <em class="term"> (comandos de software, D5)."""
    return mark_safe(_TERM.sub(r'<em class="term">\1</em>', escape(value or "")))  # noqa: S308


@register.filter(name="md")
def markdown_filter(value):
    """Markdown mínimo y seguro (ver apps/core/markdown.py)."""
    return md_lite.render(value)


@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.inclusion_tag("core/partials/course_xp.html")
def course_xp(resource):
    """Chip «+N XP» de un curso: enlaza a subir su certificado ya vinculado al curso."""
    from apps.gamification.game import resource_xp

    return {
        "resource": resource,
        "points": resource_xp(resource),
        "essential": "Esencial" in (resource.tags or []),
    }


@register.filter
def reward_xp(reward):
    """XP de un curso externo según su recompensa: trofeo = curso (100), reliquia = certificación (500)."""
    from apps.credentials.models import Credential
    from apps.gamification.game import CREDENTIAL_POINTS

    kind = Credential.Kind.CERTIFICATION if reward == "relic" else Credential.Kind.COMPLETION
    return CREDENTIAL_POINTS[kind]


# ── garabatos inline (img/doodles/*.svg) ────────────────────────────────────────────────────────
# La tinta usa currentColor: solo sigue el color del tema si el SVG va dentro del HTML.
_DOODLES = Path(__file__).resolve().parents[1] / "static" / "core" / "img" / "doodles"
_DOODLE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DOODLE_ALIAS = {"civil-estructural": "civil"}
_SVG_OPEN = re.compile(r"<svg\b([^>]*)>", re.S)


@lru_cache(maxsize=64)
def _doodle_source(name):
    path = _DOODLES / f"{name}.svg"
    if not path.is_file() or path.resolve().parent != _DOODLES.resolve():
        return ""
    svg = path.read_text(encoding="utf-8")
    svg = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(
        r"<title\b.*?</title>", "", svg, flags=re.S
    )  # decorativo: sin título para lectores
    return svg.strip()


@register.simple_tag
def doodle(name, **attrs):
    """Dibujo a mano decorativo, en línea (aria-hidden). Solo archivos de img/doodles; si falta, no devuelve nada."""
    name = _DOODLE_ALIAS.get(name, name)
    if not isinstance(name, str) or not _DOODLE_NAME.match(name):
        return ""
    svg = _doodle_source(name)
    if not svg:
        return ""
    css = escape(str(attrs.get("class", "dd")))

    def _open(match):
        inner = re.sub(
            r"\s(?:role|aria-labelledby|class|width|height)=\"[^\"]*\"", "", match.group(1)
        )
        return f'<svg{inner} class="{css}" aria-hidden="true" focusable="false">'

    return mark_safe(_SVG_OPEN.sub(_open, svg, count=1))  # noqa: S308
