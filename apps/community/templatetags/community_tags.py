from django import template
from django.db.models import Q

from .. import services

register = template.Library()


@register.inclusion_tag("community/_level_notes.html", takes_context=True)
def level_notes(context, path, level_code=""):
    """Últimas notas del capítulo abierto, para el panel de cada mundo."""
    level = path.levels.filter(code=level_code).first() if level_code else None
    qs = services.notes_for(path)
    if level is not None:  # las del capítulo y las de toda la ruta
        qs = qs.filter(Q(level=level) | Q(level__isnull=True))
    notes = list(qs[:3])
    return {
        "path": path,
        "level_code": level_code,
        "notes": notes,
        "request": context.get("request"),
    }
