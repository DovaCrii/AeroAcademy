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


@register.inclusion_tag("catalog/partials/guide.html")
def level_guide(path, current):
    """Tarjeta «Guía rápida» del nivel (vacía si la ruta no trae guía para ese nivel)."""
    ctx = guides.guide_context(path, current) or {}
    ctx["flavour"] = software.discipline_key(path)
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
