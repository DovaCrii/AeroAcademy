from django import template

from apps.catalog import guides, software

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
    }


@register.simple_tag
def route_flavour(path):
    """Variante visual de una ruta: acento de disciplina y textos de portada propios del oficio."""
    key = software.discipline_key(path)
    return {**FLAVOURS.get(key, FLAVOURS[software.ARQ]), "key": key}


FLAVOURS = {
    software.ARQ: {
        "kicker": "Levantamiento digital",
        "scene": "building",
        "scale": "ESCALA 1:500",
        "sheet": "A-101",
        "mark": "A-201",
        "content": "Corte A-A · avance personal y del equipo",
        "photo": "arquitectura",
        "levels_title": "Niveles",
        "levels_sub": "Elige un nivel en el navegador de proyecto, como en Revit.",
        "browser": "Project Browser · Levels",
    },
    software.CIV: {
        "kicker": "Topografía y diseño vial",
        "scene": "terrain",
        "scale": "ESCALA 1:1000",
        "sheet": "C-101",
        "mark": "C-201",
        "content": "Planta-perfil · avance por kilómetro",
        "photo": "civil",
        "levels_title": "Kilómetros",
        "levels_sub": "Cada kilómetro es una etapa del camino: elígela en el Explorer, como en Civil 3D.",
        "browser": "Explorer · Etapas",
    },
    software.TOP: {
        "kicker": "Topografía",
        "scene": "terrain",
        "scale": "ESCALA 1:2000",
        "sheet": "T-101",
        "mark": "T-201",
        "content": "Carta topográfica · avance por zona",
        "photo": "topografia",
        "levels_title": "Zonas",
        "levels_sub": "Elige una zona del mapa para ver sus recursos y misiones.",
        "browser": "Cartas · Zonas",
    },
    software.MEC: {
        "kicker": "Plano de taller",
        "scene": "building",
        "scale": "ESCALA 1:1",
        "sheet": "M-101",
        "mark": "M-201",
        "content": "Despiece · avance por pieza",
        "photo": "mecanica",
        "levels_title": "Piezas",
        "levels_sub": "Elige una pieza del conjunto para ver sus recursos y misiones.",
        "browser": "Árbol de montaje",
    },
    software.TRA: {
        "kicker": "Herramienta transversal",
        "scene": "building",
        "scale": "ESCALA 1:100",
        "sheet": "X-101",
        "mark": "X-201",
        "content": "Dibujo y modelado · avance por etapa",
        "photo": "mecanica",
        "levels_title": "Etapas",
        "levels_sub": "Elige una etapa para ver sus recursos y misiones.",
        "browser": "Explorador · Etapas",
    },
    software.CAP: {
        "kicker": "Captura y levantamiento",
        "scene": "terrain",
        "scale": "ESCALA 1:500",
        "sheet": "L-101",
        "mark": "L-201",
        "content": "Plan de vuelo · avance por misión",
        "photo": "topografia",
        "levels_title": "Misiones",
        "levels_sub": "Elige una misión del plan de vuelo.",
        "browser": "Plan de vuelo",
    },
}
