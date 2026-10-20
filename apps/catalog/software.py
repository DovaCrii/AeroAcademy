"""Mosaicos de software: a qué producto pertenece un recurso o una ruta.

Los mosaicos son originales (`core/img/software/<slug>.svg`), no logotipos de fabricantes. Hay cuatro familias:
Autodesk (baldosa con letra grande y banda de código), Bentley (baldosa azul con pictograma blanco), internos e IA y Datos.
Cada uno lleva además la disciplina a la que se asocia, que pinta el acento de la tarjeta.
"""

import re
from dataclasses import dataclass

from .models import Platform, Resource

# Acentos por disciplina (los colores viven en el CSS del catálogo y de los mundos).
ARQ, CIV, TOP, MEC, CAP, TRA, IAD = "arq", "civ", "top", "mec", "cap", "tra", "iad"
DISCIPLINE_LABEL = {
    ARQ: "Arquitectura",
    CIV: "Civil",
    TOP: "Topografía",
    MEC: "Mecánica",
    CAP: "Captura",
    TRA: "Transversal",
    IAD: "IA y Datos",
}
DISCIPLINE_BY_SLUG = {
    "arquitectura": ARQ,
    "civil-estructural": CIV,
    "topografia": TOP,
    "mecanica": MEC,
    "captura-rpa": CAP,
    "transversal": TRA,
    "ia-datos": IAD,
}
DISCIPLINE_SLUG_BY_KEY = {key: slug for slug, key in DISCIPLINE_BY_SLUG.items()}


@dataclass(frozen=True)
class Tile:
    code: str  # código corto (Autodesk: banda inferior del mosaico)
    slug: str  # nombre del archivo SVG
    name: str
    discipline: str
    family: str = "internal"  # familia visual: autodesk, bentley o internal

    @property
    def static_path(self):
        return f"core/img/software/{self.slug}.svg"


AUTODESK, BENTLEY, INTERNAL, IA = "autodesk", "bentley", "internal", "ia"
FAMILY_LABEL = {
    AUTODESK: "Autodesk",
    BENTLEY: "Bentley Systems",
    INTERNAL: "Topografía, GIS y captura",
    IA: "IA y Datos",
}

TILES = {
    t.slug: t
    for t in (
        # Autodesk: baldosa con letra grande y banda de código
        Tile("RVT", "revit", "Revit", ARQ, AUTODESK),
        Tile("C3D", "civil3d", "Civil 3D", CIV, AUTODESK),
        Tile("CAD", "autocad", "AutoCAD", TRA, AUTODESK),
        Tile("FOR", "forma", "Forma", ARQ, AUTODESK),
        Tile("DOC", "acc", "Autodesk Docs / ACC", ARQ, AUTODESK),
        Tile("DYN", "dynamo", "Dynamo", ARQ, AUTODESK),
        Tile("NAV", "navisworks", "Navisworks", MEC, AUTODESK),
        Tile("RCP", "recap", "ReCap", CAP, AUTODESK),
        Tile("INF", "infraworks", "InfraWorks", CIV, AUTODESK),
        Tile("P3D", "plant-3d", "Plant 3D", MEC, AUTODESK),
        # Bentley: baldosa azul con pictograma blanco
        Tile("MS", "microstation", "MicroStation", TRA, BENTLEY),
        Tile("ORD", "openroads", "OpenRoads Designer", CIV, BENTLEY),
        Tile("OBR", "openbridge", "OpenBridge", CIV, BENTLEY),
        Tile("OBD", "openbuildings", "OpenBuildings Designer", ARQ, BENTLEY),
        Tile("OPL", "openplant", "OpenPlant", MEC, BENTLEY),
        Tile("OFL", "openflows", "OpenFlows", CIV, BENTLEY),
        Tile("STD", "staad", "STAAD", CIV, BENTLEY),
        Tile("ITW", "itwin", "iTwin", CIV, BENTLEY),
        Tile("LRT", "lumenrt", "LumenRT", ARQ, BENTLEY),
        Tile("PW", "projectwise", "ProjectWise", ARQ, BENTLEY),
        Tile("ICM", "itwin-capture", "iTwin Capture", CAP, BENTLEY),
        Tile("SYN", "synchro", "SYNCHRO", CIV, BENTLEY),
        Tile("DSC", "descartes", "Descartes", CAP, BENTLEY),
        # Internos
        Tile("TBC", "tbc", "Trimble Business Center", TOP),
        Tile("GIS", "gis", "ArcGIS / GIS", TOP),
        Tile("RPA", "dgac", "DGAC / RPAS", CAP),
        # IA y Datos: baldosa de color con pictograma blanco genérico (sin logotipos)
        Tile("IA", "ia", "IA", IAD, IA),
        Tile("TRM", "terminal", "Terminal", IAD, IA),
        Tile("GIT", "git", "Git", IAD, IA),
        Tile("CLC", "claude-code", "Claude Code", IAD, IA),
        Tile("MCP", "mcp", "MCP", IAD, IA),
        Tile("AGT", "agentes", "Agentes IA", IAD, IA),
        Tile("PY", "python", "Python", IAD, IA),
        Tile("QGS", "qgis", "QGIS", IAD, IA),
        Tile("GEE", "gee", "Earth Engine", IAD, IA),
        Tile("PBI", "powerbi", "Power BI", IAD, IA),
        Tile("SQL", "sql", "SQL", IAD, IA),
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
    "plant-3d": "plant-3d",
    "autocad": "autocad",
    "openplant": "openplant",
    "openflows": "openflows",
    "staad": "staad",
    "itwin": "itwin",
    "lumenrt": "lumenrt",
    "projectwise": "projectwise",
    "itwin-capture": "itwin-capture",
    "synchro": "synchro",
    "descartes": "descartes",
    "infraworks": "infraworks",
    # IA y Datos
    "claude": "ia",
    "claude-code": "claude-code",
    "claude-api": "agentes",
    "mcp": "mcp",
    "python": "python",
    "git": "git",
    "qgis": "qgis",
    "earth-engine": "gee",
    "power-bi": "powerbi",
    "sql": "sql",
}

# Icono propio de cada ruta (slug de LearningPath → archivo img/software/<stem>.svg). Nunca se repite entre rutas.
# Son pictogramas originales; si se incorpora un logotipo oficial, se cambia aquí el archivo de ESA ruta (ver docs/ICONOS.md).
ROUTE_ICON = {
    slug: f"ruta-{slug}"
    for slug in (
        "autocad", "civil-3d", "forma-revit", "forma-coordinacion", "plant-3d",
        "bentley-learn", "bentley-itwin", "bentley-lumenrt", "bentley-openbuildings", "bentley-openplant",
        "bentley-projectwise", "bim-101", "topografia-101", "ia-101", "herramientas-ia", "vibe-coding",
        "agentes-ia", "claude-code-mcp", "python-datos-101", "data-science-aplicada", "datos-reportes",
        "geospatial-data-science", "dgac-rpas", "microstation-jej",
    )
}  # fmt: skip


def route_icon(slug):
    """Nombre (sin .svg) del icono propio de una ruta, o '' si no tiene."""
    return ROUTE_ICON.get(slug, "")


# Palabras del título (en minúsculas) → mosaico. El orden no importa: se ordena por posición en el título.
TITLE_KEYWORDS = [
    (r"\brevit\b", "revit"),
    (r"bim for (architectural|mep|structural)|^architectural modeling by|bim foundations", "revit"),
    (r"civil 3d|civil3d|bim for civil", "civil3d"),
    (r"plant 3d|plant3d", "plant-3d"),
    (r"autocad(?! plant)", "autocad"),
    (r"\bforma\b(?! data management)", "forma"),
    (r"forma data management|\bdocs\b|autodesk construction cloud|\bacc\b", "acc"),
    (r"dynamo", "dynamo"),
    (r"microstation", "microstation"),
    (r"openroads|road (designer|modeler)", "openroads"),
    (r"openbridge|bridge modeler", "openbridge"),
    (r"openbuildings|bim modeler", "openbuildings"),
    (r"openplant", "openplant"),
    (r"openflows|watergems|sewergems|stormcad", "openflows"),
    (r"staad", "staad"),
    (r"itwin capture|contextcapture|context capture", "itwin-capture"),
    (r"itwin(?! capture)", "itwin"),
    (r"lumenrt", "lumenrt"),
    (r"projectwise", "projectwise"),
    (r"synchro", "synchro"),
    (r"descartes", "descartes"),
    (r"infraworks", "infraworks"),
    (r"dgac|rpas|\bdrones?\b", "dgac"),
    (r"recap", "recap"),
    (r"navisworks", "navisworks"),
    (r"trimble business center|\btbc\b", "tbc"),
    (r"arcgis|\bgis\b", "gis"),
]
_COMPILED = [(re.compile(rx), slug) for rx, slug in TITLE_KEYWORDS]

# Plataformas o vendors con un solo producto de referencia: sirven de último recurso.
VENDOR_FALLBACK = {"esri": "gis", "trimble": "tbc", "bentley": "microstation", "dji": "dgac"}
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
    if (
        not slugs
    ):  # rutas internas (p. ej. el diploma RPAS) sin productos de catálogo: el título manda
        return tiles_from_title(path.title, limit)
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
        ("openbuildings", ARQ),
        ("plant-3d", MEC),
        ("openplant", MEC),
        ("autocad", TRA),
        ("microstation", TRA),
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
    "revit", "civil3d", "forma", "autocad", "plant-3d", "acc", "dynamo", "navisworks", "recap", "infraworks",
    "microstation", "openroads", "openbridge", "openbuildings", "openplant", "openflows", "staad",
    "itwin", "lumenrt", "projectwise", "itwin-capture", "synchro", "descartes",
    "tbc", "gis", "dgac",
    "ia", "terminal", "git", "claude-code", "mcp", "agentes", "python", "qgis", "gee", "powerbi", "sql",
]  # fmt: skip

# ---- áreas del catálogo ----------------------------------------------------------------------------------------
# Cada recurso pertenece a UNA área (el mapa del catálogo suma todos): su familia de mosaico o, si no tiene producto,
# la deducida de su ruta. «general» es el conocimiento transversal (BIM y topografía base).
GENERAL = "general"
AREA_ORDER = (AUTODESK, BENTLEY, IA, INTERNAL, GENERAL)
AREA_LABEL = {**FAMILY_LABEL, GENERAL: "Conocimiento general"}
FAMILIES = (AUTODESK, BENTLEY, IA, INTERNAL)  # las que tienen filas por producto
# vendor (slug) de la ruta → área, para los recursos sin producto ni mosaico en su ruta
PATH_VENDOR_AREA = {
    "autodesk": AUTODESK,
    "bentley": BENTLEY,
    "anthropic": IA,
    "kaggle": IA,
    "microsoft": IA,
    "open-source": IA,
    "aeroacademy": INTERNAL,
}
FAMILY_DISCIPLINE = {AUTODESK: ARQ, BENTLEY: CIV, INTERNAL: TOP, IA: IAD, GENERAL: TRA}
AREA_TILE = {IA: "ia"}  # mosaico genérico de las áreas cuyos recursos no traen producto
STARTERS = 4  # tarjetas de «Para empezar» en cada área de la portada del catálogo


def area_for_resource(resource, paths_by_id, links, general_ids=frozenset()):
    """Área de un recurso: la familia de su primer mosaico; si no tiene, la de su ruta; si no, general; si no, el vendor.

    `paths_by_id` son las rutas publicadas (con `vendor` y `products` precargados), `links` {recurso: [id de ruta]}
    y `general_ids` los recursos con la etiqueta «Conocimiento general». No hace consultas. Último recurso: la
    familia interna, para que ningún recurso quede sin área.
    """
    tiles = software_for_resource(resource, 1)
    if tiles:
        return tiles[0].family
    paths = sorted(
        (paths_by_id[i] for i in links.get(resource.pk, ()) if i in paths_by_id),
        key=lambda p: p.title,
    )
    for path in paths:
        by_path = software_for_path(path, 1)
        if by_path:
            return by_path[0].family
    if resource.pk in general_ids:
        return GENERAL
    for path in paths:
        area = PATH_VENDOR_AREA.get(getattr(getattr(path, "vendor", None), "slug", ""))
        if area:
            return area
    return INTERNAL


def areas_of(resources, paths, links, general_ids=frozenset()):
    """{pk del recurso: área}."""
    by_id = {p.pk: p for p in paths}
    return {r.pk: area_for_resource(r, by_id, links, general_ids) for r in resources}


def _row(key, name, discipline, family, items, per_row, tile=None):
    return {
        "tile": tile,
        "key": key,
        "name": name,
        "discipline": discipline,
        "family": family,
        "items": items[:per_row],
        "total": len(items),
        "more": max(0, len(items) - per_row),
    }


def group_by_software(resources, per_row=8, areas=None):
    """[{tile, key, name, items, total, more}] en el orden de ROW_ORDER; el recurso va en la fila de su primer mosaico.

    Sin `areas` (pk → área), los recursos sin mosaico quedan fuera (siguen en el listado completo). Con `areas`, los
    que no tienen producto pero sí familia se juntan en la fila «Más de <área>» (clave `more-<familia>`, sin mosaico)
    al final de su área; el conocimiento general no lleva filas.
    """
    buckets, more = {}, {}
    for r in resources:
        tiles = software_for_resource(r, 1)
        if tiles:
            buckets.setdefault(tiles[0].slug, []).append(r)
        elif areas and areas.get(r.pk) in FAMILIES:
            more.setdefault(areas[r.pk], []).append(r)
    rows = []
    for slug in ROW_ORDER:
        items = buckets.get(slug)
        if items:
            t = TILES[slug]
            rows.append(_row(slug, t.name, t.discipline, t.family, items, per_row, tile=t))
    for family in FAMILIES:
        if family in more:
            rows.append(
                _row(
                    f"more-{family}",
                    f"Más de {FAMILY_LABEL[family]}",
                    FAMILY_DISCIPLINE[family],
                    family,
                    more[family],
                    per_row,
                )
            )
    return rows


def starters(rows, limit=STARTERS):
    """Hasta `limit` recursos para empezar: uno por producto, en rondas (el orden de cada fila ya trae lo
    esencial primero, luego lo oficial)."""
    out, rank = [], 0
    while len(out) < limit and any(len(r["items"]) > rank for r in rows):
        for row in rows:
            if len(out) < limit and len(row["items"]) > rank:
                out.append(row["items"][rank])
        rank += 1
    return out


def vendor_sections(rows, preview=STARTERS):
    """Agrupa las filas por área: [{key, label, rows, pack, total, starters}].

    `pack` son todos los mosaicos de la familia (con su cantidad de recursos) y `starters` las tarjetas de
    «Para empezar». Sin filas, no hay sección. Orden: Autodesk, Bentley, IA y Datos, Topografía.
    """
    totals = {r["key"]: r["total"] for r in rows}
    sections = []
    for family in FAMILIES:
        fam_rows = [r for r in rows if r["family"] == family]
        if not fam_rows:
            continue
        pack = [
            {"tile": TILES[s], "total": totals.get(s, 0)}
            for s in ROW_ORDER
            if TILES[s].family == family
        ]
        sections.append(
            {
                "key": family,
                "label": FAMILY_LABEL[family],
                "rows": fam_rows,
                "pack": pack,
                "products": [p for p in pack if p["total"]],
                "starters": starters(fam_rows, preview),
                "total": sum(r["total"] for r in fam_rows),
            }
        )
    return sections


def catalog_map(resources, areas):
    """Mapa del catálogo: [{key, label, total, products: [{tile, total}], anchor}] de las 5 áreas, en su orden.

    `total` cuenta TODOS los recursos del área (la suma es el catálogo completo); `products` solo los productos
    que tienen recursos, en el orden de ROW_ORDER.
    """
    totals = dict.fromkeys(AREA_ORDER, 0)
    by_tile = {}
    for r in resources:
        area = areas.get(r.pk)
        if area in totals:
            totals[area] += 1
        tiles = software_for_resource(r, 1)
        if tiles:
            by_tile[tiles[0].slug] = by_tile.get(tiles[0].slug, 0) + 1
    out = []
    for area in AREA_ORDER:
        products = [
            {"tile": TILES[s], "total": by_tile[s]}
            for s in ROW_ORDER
            if s in by_tile and TILES[s].family == area
        ]
        out.append(
            {
                "key": area,
                "label": AREA_LABEL[area],
                "tile": products[0]["tile"] if products else TILES.get(AREA_TILE.get(area, "")),
                "total": totals[area],
                "products": products,
                "anchor": "conocimiento-general" if area == GENERAL else f"vendor-{area}",
            }
        )
    return out


def vendor_key(path):
    """Familia visual de una ruta: la de su fabricante (autodesk, bentley, internal)."""
    slug = getattr(getattr(path, "vendor", None), "slug", "")
    return slug if slug in (AUTODESK, BENTLEY) else INTERNAL


def resource_ids_for_software(resources, slug):
    return [r.pk for r in resources if (t := software_for_resource(r, 1)) and t[0].slug == slug]
