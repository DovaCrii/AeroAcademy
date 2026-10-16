from django import template
from django.utils.safestring import mark_safe

from .. import services

register = template.Library()


@register.simple_tag
def avatar(person, size=32, view="bust", frame=True):
    """Figurita de una persona. El SVG sale del catálogo: nada del usuario entra.

    `size` debe ser un múltiplo entero del ancho de la vista (`head` 16, `bust` 24, `full` 32). Con `frame` el SVG va
    dentro de un contenedor con el marco de rareza; sin él es solo el SVG (cabecera, tablas).
    """
    cfg = services.person_config(person)
    svg = services.svg_sized(
        cfg,
        size,
        title=f"Avatar de {person.name}",
        view=view if view in {"full", "bust", "head"} else "bust",
        bg_alt=services.auto_background(person, cfg),
    )
    return services.framed(svg, cfg) if frame else mark_safe(svg)  # noqa: S308
