import re

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
