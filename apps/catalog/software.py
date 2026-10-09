"""Mosaicos de software: a qué producto pertenece un recurso o una ruta.

Los mosaicos son monogramas originales (`core/img/software/<slug>.svg`), no logotipos de fabricantes.
Cada uno lleva además la disciplina a la que se asocia, que pinta el acento de la tarjeta.
"""

import re
from dataclasses import dataclass

from .models import Platform, Resource

# Acentos por disciplina (los colores viven en el CSS del catálogo y de los mundos).
ARQ, CIV, TOP, MEC, CAP = "arq", "civ", "top", "mec", "cap"
DISCIPLINE_LABEL = {
    ARQ: "Arquitectura",
    CIV: "Civil",
    TOP: "Topografía",
    MEC: "Mecánica",
    CAP: "Captura",
}
DISCIPLINE_BY_SLUG = {
    "arquitectura": ARQ,
    "civil-estructural": CIV,
    "topografia": TOP,
    "mecanica": MEC,
    "captura-rpa": CAP,
}


@dataclass(frozen=True)
class Tile:
    code: str  # monograma que se ve en el mosaico
    slug: str  # nombre del archivo SVG
    name: str
    discipline: str

    @property
    def static_path(self):
        return f"core/img/software/{self.slug}.svg"


TILES = {
    t.slug: t
    for t in (
        Tile("Rv", "revit", "Revit", ARQ),
        Tile("C3D", "civil3d", "Civil 3D", CIV),
        Tile("ACAD", "autocad", "AutoCAD", MEC),
        Tile("Fm", "forma", "Forma", ARQ),
        Tile("ACC", "acc", "Autodesk Docs / ACC", ARQ),
        Tile("Dy", "dynamo", "Dynamo", ARQ),
        Tile("MS", "microstation", "MicroStation", CIV),
        Tile("ORD", "openroads", "OpenRoads Designer", CIV),
        Tile("OBr", "openbridge", "OpenBridge", CIV),
        Tile("OBD", "openbuildings", "OpenBuildings Designer", ARQ),
        Tile("RC", "recap", "ReCap", CAP),
        Tile("Nw", "navisworks", "Navisworks", MEC),
        Tile("TBC", "tbc", "Trimble Business Center", TOP),
        Tile("GIS", "gis", "ArcGIS / GIS", TOP),
    )
}

# slug de Product (seed/vendors.json) → mosaico
PRODUCT_TILE = {
    "revit": "revit",
    "forma": "forma",
    "civil-3d": "civil3d",
    "recap": "recap",
    "navisworks": "navisworks",
    "microstation": "microstation",
    "openroads-designer": "openroads",
    "openbridge": "openbridge",
    "openbuildings": "openbuildings",
    "tbc": "tbc",
    "arcgis-pro": "gis",
}

# Palabras del título (en minúsculas) → mosaico. El orden no importa: se ordena por posición en el título.
TITLE_KEYWORDS = [
    (r"\brevit\b", "revit"),
    (r"bim for (architectural|mep|structural)|^architectural modeling by|bim foundations", "revit"),
    (r"civil 3d|civil3d|bim for civil", "civil3d"),
    (r"autocad", "autocad"),
    (r"\bforma\b(?! data management)", "forma"),
    (r"forma data management|\bdocs\b|autodesk construction cloud|\bacc\b", "acc"),
    (r"dynamo", "dynamo"),
    (r"microstation", "microstation"),
    (r"openroads|road (designer|modeler)", "openroads"),
    (r"openbridge|bridge modeler", "openbridge"),
    (r"openbuildings|bim modeler", "openbuildings"),
    (r"recap", "recap"),
    (r"navisworks", "navisworks"),
    (r"trimble business center|\btbc\b", "tbc"),
    (r"arcgis|\bgis\b", "gis"),
]
_COMPILED = [(re.compile(rx), slug) for rx, slug in TITLE_KEYWORDS]

# Plataformas o vendors con un solo producto de referencia: sirven de último recurso.
VENDOR_FALLBACK = {"esri": "gis", "trimble": "tbc", "bentley": "microstation"}
VENDOR_BY_PLATFORM = {"bentley-learn": "bentley"}
PLATFORM_FALLBACK = {"geocom-cursos": "tbc", "esri-training": "gis", "trimble-learning": "tbc"}


def tile(slug):
    return TILES.get(slug)


def tiles_from_title(title, limit=2):
    """Mosaicos que nombra el título, en el orden en que aparecen."""
    text = (title or "").lower()
    found = {}
    for rx, slug in _COMPILED:
        m = rx.search(text)
        if m and slug not in found:
            found[slug] = m.start()
    ordered = sorted(found, key=found.get)
    # «Revit … Forma»: el segundo producto solo suma si no es un detalle de ruta (máx. `limit`).
    return [TILES[s] for s in ordered[:limit]]


def _prefetched(resource, name):
    """Objetos relacionados solo si ya vienen precargados: pintar mosaicos nunca suma consultas."""
    cache = getattr(resource, "_prefetched_objects_cache", {})
    return cache.get(name)


def software_for_resource(resource, limit=2):
    """Mosaicos de un recurso: productos asignados, si no el título, si no la plataforma o el vendor.

    Sin consultas extra: `products` y `platform` se usan solo si vienen precargados (`resource_queryset`);
    en las listas de una ruta basta el título.
    """
    products = _prefetched(resource, "products")
    slugs = [PRODUCT_TILE[p.slug] for p in products or [] if p.slug in PRODUCT_TILE]
    if slugs:
        return [TILES[s] for s in dict.fromkeys(slugs)][:limit]
    by_title = tiles_from_title(resource.title, limit)
    if by_title:
        return by_title
    if Resource.platform.is_cached(resource):
        platform = resource.platform
        fallback = PLATFORM_FALLBACK.get(platform.slug)
        if not fallback and platform.vendor_id and Platform.vendor.is_cached(platform):
            fallback = VENDOR_FALLBACK.get(platform.vendor.slug)
        elif not fallback:
            fallback = VENDOR_FALLBACK.get(VENDOR_BY_PLATFORM.get(platform.slug, ""))
        return [TILES[fallback]] if fallback else []
    return []


def software_for_path(path, limit=4):
    """Mosaicos de una ruta: sus productos (portada y encabezados)."""
    slugs = [PRODUCT_TILE[p.slug] for p in path.products.all() if p.slug in PRODUCT_TILE]
    return [TILES[s] for s in dict.fromkeys(slugs)][:limit]


def discipline_key(path):
    """Acento de disciplina de una ruta: por su producto principal, si no por su primera disciplina."""
    products = {p.slug for p in path.products.all()}
    for slug, key in (
        ("civil-3d", CIV),
        ("openroads-designer", CIV),
        ("tbc", TOP),
        ("revit", ARQ),
        ("forma", ARQ),
    ):
        if slug in products:
            return key
    for d in sorted(path.disciplines.all(), key=lambda d: d.order):
        if d.slug in DISCIPLINE_BY_SLUG:
            return DISCIPLINE_BY_SLUG[d.slug]
    return ARQ


def discipline_for_resource(resource):
    """Acento de una tarjeta del catálogo: el de su primer mosaico; Arquitectura si no hay ninguno."""
    tiles = software_for_resource(resource, 1)
    return tiles[0].discipline if tiles else ARQ


# ---- nivel y tipo de una tarjeta (sin campo nuevo: se deduce del recurso) ----------------------------------

LEVELS = {"fundamental": "Fundamental", "intermedio": "Intermedio", "avanzado": "Avanzado"}
_ADVANCED = re.compile(
    r"certification prep|professional certification|accredited .*professional|^project \||advanced|"
    r"\bapi\b|automat|developer|certified professional|add-in"
)
_BASIC = re.compile(
    r"introduction|basics|getting started|in 90 minutes|fundamental|navigating|foundations|"
    r"set up|conceptual|quickstart|catalog|catálogo|^autodesk certified user|learning hub|accredited user"
)


def level_for_resource(resource):
    """(clave, etiqueta) de nivel: Fundamental, Intermedio o Avanzado, según tipo, etiquetas y título."""
    title = (resource.title or "").lower()
    tags = " ".join(resource.tags or []).lower()
    if resource.kind == "exam" or "prepara certificación" in tags or _ADVANCED.search(title):
        key = "avanzado"
    elif _BASIC.search(title) or resource.kind in ("collection", "article"):
        key = "fundamental"
    else:
        key = "intermedio"
    return key, LEVELS[key]


TYPE_LABEL = {
    "course": "On demand",
    "module": "On demand",
    "tutorial": "On demand",
    "learning_plan": "Plan de aprendizaje",
    "exam": "Examen",
    "collection": "Colección",
    "guide": "Guía",
    "article": "Artículo",
}


def type_label(resource):
    return TYPE_LABEL.get(resource.kind) or resource.get_kind_display()


# ---- filas por producto del catálogo ------------------------------------------------------------------------

ROW_ORDER = [
    "revit", "civil3d", "forma", "autocad", "acc", "dynamo", "microstation", "openroads",
    "openbridge", "openbuildings", "recap", "navisworks", "tbc", "gis",
]  # fmt: skip


def group_by_software(resources, per_row=8):
    """[{tile, items, total}] en el orden de ROW_ORDER; el recurso va en la fila de su primer mosaico.

    Los recursos sin mosaico quedan fuera (siguen en el listado completo).
    """
    buckets = {}
    for r in resources:
        tiles = software_for_resource(r, 1)
        if tiles:
            buckets.setdefault(tiles[0].slug, []).append(r)
    rows = []
    for slug in ROW_ORDER:
        items = buckets.get(slug)
        if items:
            rows.append(
                {
                    "tile": TILES[slug],
                    "items": items[:per_row],
                    "total": len(items),
                    "more": max(0, len(items) - per_row),
                }
            )
    return rows


def resource_ids_for_software(resources, slug):
    return [r.pk for r in resources if (t := software_for_resource(r, 1)) and t[0].slug == slug]
