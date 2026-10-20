from django import template

from apps.catalog import figures, guides, software

register = template.Library()


@register.inclusion_tag("catalog/partials/sw_tiles.html")
def sw_tiles(resource, size="sm", limit=2):
    """Mosaicos del software al que está ligado un recurso."""
    return {"tiles": software.software_for_resource(resource, limit), "size": size}


@register.inclusion_tag("catalog/partials/sw_tiles.html")
def path_tiles(path, size="md", limit=4):
    """Mosaicos de los productos de una ruta."""
    return {"tiles": software.software_for_path(path, limit), "size": size}


@register.simple_tag
def route_icon_src(path):
    """Ruta estática del icono propio de una ruta ("" si no tiene)."""
    stem = software.route_icon(path.slug)
    return f"core/img/software/{stem}.svg" if stem else ""


@register.inclusion_tag("core/partials/route_card.html")
def route_card(path, variant=""):
    """Tarjeta única de una ruta (portada, /rutas/, catálogo y foro): icono, disciplinas, avance y UN botón.

    `path.cta` lo pone la vista con `paths.services.attach_ctas` (consultas fijas). `variant`: «compact» (portada:
    sin descripción) o «notes» (foro: el botón lleva a las notas de la ruta y hay un enlace «Ir a la ruta»).
    """
    from django.urls import reverse

    key = software.discipline_key(path)
    discs = sorted(path.disciplines.all(), key=lambda d: d.order)
    main_slug = software.DISCIPLINE_SLUG_BY_KEY.get(key, "")
    cta = getattr(path, "cta", None) or {}
    if variant == "notes":
        cta = {
            "label": "Ver notas →",
            "url": reverse("community:path_notes", args=[path.slug]),
            "pct": 0,
        }
    return {
        "path": path,
        "variant": variant,
        "cta": cta,
        "ico": route_icon_src(path),
        "disc_slug": main_slug,
        "disc_label": software.DISCIPLINE_LABEL.get(key, ""),
        "also": [d.name for d in discs if d.slug != main_slug and d.slug != "transversal"][:3],
    }


@register.inclusion_tag("core/partials/crumbs.html")
def route_crumbs(path, level=None, here=""):
    """Migas: Inicio › Rutas › Disciplina › Ruta › Nivel N (o `here`, p. ej. «Notas»)."""
    key = software.discipline_key(path)
    has = software.DISCIPLINE_SLUG_BY_KEY.get(key) in {d.slug for d in path.disciplines.all()}
    return {
        "path": path,
        "discipline": software.DISCIPLINE_LABEL.get(key, "") if has else "",
        "level": level,
        "here": here,
    }


@register.simple_tag
def vendor_family(path):
    """Familia visual del fabricante de una ruta: autodesk, bentley o internal."""
    return software.vendor_key(path)


@register.inclusion_tag("catalog/partials/guide.html")
def level_guide(path, current, num=""):
    """Tarjeta «Guía rápida» del nivel (vacía si la ruta no trae guía para ese nivel)."""
    ctx = guides.guide_context(path, current) or {}
    ctx["flavour"] = software.discipline_key(path)
    ctx["num"] = num
    return ctx


@register.simple_tag
def card_meta(resource):
    """Datos de una tarjeta del catálogo: mosaicos, acento de disciplina, nivel y tipo."""
    tiles = software.software_for_resource(resource, 2)
    key, label = software.level_for_resource(resource)
    return {
        "tiles": tiles,
        "name": " + ".join(t.name for t in tiles),
        "disc": tiles[0].discipline if tiles else software.ARQ,
        "level": key,
        "level_label": label,
        "type": software.type_label(resource),
        "kind_label": resource.get_kind_display(),  # «Curso», «Examen»…: el tipo, sin repetirlo
        "paid": not resource.is_free,  # solo se marca lo de pago: «gratuito» es lo normal
    }


@register.simple_tag
def route_figure(path):
    """Figura de la ruta (`apps/catalog/figures.py`): clave, plantilla y rótulos propios de su tema."""
    return figures.for_path(path)


@register.simple_tag
def route_flavour(path):
    """Acento de color de la ruta: el de su figura (los textos salen de `route_figure`, no de la disciplina)."""
    return {"key": figures.for_path(path)["accent"]}
