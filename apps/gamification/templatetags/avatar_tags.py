from django import template
from django.utils.safestring import mark_safe

from .. import services

register = template.Library()


@register.simple_tag
def avatar(person, size=32, view="bust", frame=True):
    """Figurita de una persona. El SVG sale del catálogo: nada del usuario entra."""
    cfg = services.person_config(person)
    title = f"Avatar de {person.name}"
    return mark_safe(  # noqa: S308
        services.svg_sized(
            cfg,
            size,
            title=title,
            view=view if view in {"full", "bust"} else "bust",
            frame=bool(frame),
        )
    )
