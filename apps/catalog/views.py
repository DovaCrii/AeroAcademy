from collections import Counter

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.credentials import services as credential_services
from apps.paths import services as path_services
from apps.paths.models import LearningPath

from . import official, services, software
from .models import Discipline, Platform, Resource

# Cómo se agrupan los tipos para filtrar rápido (pestañas del catálogo).
KIND_GROUPS = [
    ("", "Todo"),
    ("course", "Cursos"),
    ("module", "Módulos"),
    ("tutorial", "Tutoriales"),
    ("learning_plan", "Planes"),
    ("exam", "Exámenes"),
    ("collection", "Colecciones"),
    ("guide", "Guías"),
    ("article", "Artículos"),
]


PAGE_SIZE = 24  # resultados por página
PRODUCT_PAGE_SIZE = 48  # la vista de un producto (`?software=`): el mayor (27) cabe entero


def _general_section(request, f, show_rows):
    """Sección «Conocimiento general · transversal»: las rutas generales y cuántos recursos tienen la etiqueta.

    Número fijo de consultas (rutas, etiquetas, recursos, avance): no crece con los datos. Las tarjetas de recurso
    viven en `?general=1`. Devuelve None si no hay nada que mostrar o si el filtro activo es otro.
    """
    if not (show_rows or f["general"]):
        return None
    paths = services.general_paths()
    total = services.resource_queryset(general=True).count()  # solo los que siguen en una ruta
    if not paths and not total:
        return None
    paths = (
        path_services.attach_ctas(request.user, paths) if paths else []
    )  # avance y botón: consultas fijas
    return {"paths": paths, "total": total}


def resources(request):
    """Catálogo: buscar por palabras, filtrar por ruta, tipo y plataforma; lo esencial va primero."""
    params = request.GET
    kind = params.get("kind", "")
    kind = kind if kind in Resource.Kind.values else ""
    paths = list(
        LearningPath.objects.filter(is_published=True)
        .select_related("vendor")
        .prefetch_related("products", "disciplines")
        .order_by("title")
    )
    disciplines = list(Discipline.objects.filter(paths__is_published=True).distinct())
    discipline = params.get("discipline", "")
    discipline = discipline if discipline in {d.slug for d in disciplines} else ""
    path = params.get("ruta", "")
    path = path if path in {p.slug for p in paths} else ""
    vendor = params.get("vendor", "")
    vendor = vendor if vendor in software.AREA_LABEL else ""
    f = {
        "vendor": vendor,
        "platform": params.get("platform", ""),
        "kind": kind,
        "free": params.get("free") == "1",
        "cert": params.get("cert") == "1",
        "essential": params.get("esencial") == "1",
        "general": params.get("general") == "1",
        "path": path,
        "discipline": discipline,
        "q": params.get("q", "").strip()[:100],
    }
    software_slug = params.get("software", "")
    software_slug = software_slug if software_slug in software.TILES else ""
    f["software"] = software_slug
    others = any(v for k, v in f.items() if k != "vendor")
    only_vendor = vendor in software.FAMILIES and not others
    filtered = any(f.values())
    plain = params.get("todo") != "1" and "page" not in params
    show_rows = (not filtered or only_vendor) and plain
    portada = show_rows and not vendor  # el mapa y la vitrina por área
    # La lista completa (con sus productos precargados) se lee una sola vez: da el área de cada recurso (para el
    # filtro «Proveedor» y sus conteos), la vista por producto y la portada. Consultas fijas, no crecen con los datos.
    every = list(services.resource_queryset())
    links = services.published_path_links()
    areas = software.areas_of(every, paths, links, set(services.general_ids()))
    # Avance de QUIEN MIRA en las plataformas oficiales (una consulta: sus credenciales); nunca el de otras personas.
    states = credential_services.states_by_resource(request.user)
    progress = official.progress(every, areas, states, paths, links)
    ids = None
    if software_slug:
        ids = software.resource_ids_for_software(every, software_slug)
    if vendor:
        in_area = {pk for pk, area in areas.items() if area == vendor}
        ids = list(in_area) if ids is None else [pk for pk in ids if pk in in_area]
    qs = services.resource_queryset(
        ids=ids,
        platform=f["platform"],
        kind=kind,
        free=f["free"],
        cert=f["cert"],
        q=f["q"],
        path=path,
        essential=f["essential"],
        general=f["general"],
        discipline=discipline,
    )
    rows, sections, area_map = [], [], []
    if show_rows:  # sin filtros (o solo un proveedor): filas por producto
        scoped = [r for r in every if areas.get(r.pk) == vendor] if vendor else every
        rows = software.group_by_software(scoped, areas=areas)
        sections = software.vendor_sections(rows)
        for sec in sections:
            sec["progress"] = progress.get(sec["key"])
        cards = (
            [r for row in rows for r in row["items"]]
            if vendor
            else [r for sec in sections for r in sec["starters"]]
        )
        in_paths = services.published_paths_for([r.pk for r in cards])
        for r in cards:
            r.in_paths = in_paths.get(r.pk, [])
        official.mark_cards(cards, areas, states)
    general = _general_section(request, f, portada)
    if portada:
        area_map = software.catalog_map(every, areas)
        for a in area_map:
            a["progress"] = progress.get(a["key"])
    page = None
    if not show_rows:
        size = PRODUCT_PAGE_SIZE if software_slug else PAGE_SIZE
        page = Paginator(qs, size).get_page(params.get("page"))
        in_paths = services.published_paths_for([r.pk for r in page])
        for r in page:
            r.in_paths = in_paths.get(r.pk, [])
        official.mark_cards(page, areas, states)

    platforms = list(Platform.objects.filter(resources__isnull=False).distinct())
    counts = dict(Resource.objects.values_list("kind").annotate(n=Count("pk")))
    kinds = [(value, label, counts.get(value, 0)) for value, label in KIND_GROUPS]
    kinds = [k for k in kinds if k[0] == "" or k[2]]

    query = params.copy()
    query.pop("page", None)
    kind_label = dict(KIND_GROUPS).get(kind, "")
    software_tile = software.TILES.get(software_slug)
    labels = {
        "vendor": software.AREA_LABEL.get(vendor, ""),
        "q": f"«{f['q']}»",
        "discipline": next((d.name for d in disciplines if d.slug == discipline), ""),
        "kind": kind_label,
        "ruta": next((p.title for p in paths if p.slug == path), ""),
        "platform": next((p.name for p in platforms if p.slug == f["platform"]), ""),
        "free": "Gratuito",
        "cert": "Con certificado",
        "esencial": "Solo esenciales",
        "general": "Conocimiento general",
        "software": software_tile.name if software_tile else "",
    }
    active = {
        "vendor": vendor,
        "q": f["q"],
        "discipline": discipline,
        "kind": kind,
        "ruta": path,
        "platform": f["platform"],
        "free": f["free"],
        "cert": f["cert"],
        "esencial": f["essential"],
        "general": f["general"],
        "software": software_slug,
    }
    chips = []
    for key, on in active.items():  # cada chip es un enlace al mismo catálogo sin ese parámetro
        if not (on and labels[key]):
            continue
        rest = params.copy()
        for drop in (key, "page"):
            rest.pop(drop, None)
        chips.append({"key": key, "label": labels[key], "query": rest.urlencode()})
    groups = path_services.group_by_area(paths)
    crumbs = []
    if software_tile:
        crumbs = [
            (software.FAMILY_LABEL[software_tile.family], f"?vendor={software_tile.family}"),
            (software_tile.name, ""),
        ]
    elif only_vendor:
        crumbs = [(software.AREA_LABEL[vendor], "")]
    counted = Counter(areas.values())
    area_totals = {key: counted.get(key, 0) for key in software.AREA_ORDER}
    vendor_options = [
        (key, software.AREA_LABEL[key], area_totals[key]) for key in software.AREA_ORDER
    ]
    return render(
        request,
        "catalog/resources.html",
        {
            "page": page,
            "platforms": platforms,
            "disciplines": disciplines,
            "chips": chips,
            "route_groups": groups,
            "kinds": kinds,
            "total": Resource.objects.count(),
            "paths": paths,
            "essential_count": len(services.essential_ids()),
            "cert_count": Resource.objects.filter(
                Q(grants_completion_certificate=True) | Q(kind=Resource.Kind.EXAM)
            ).count(),
            "f": f,
            "filtered": filtered,
            "show_rows": show_rows,
            "portada": portada,
            "vendor_view": show_rows and bool(vendor),
            "general": general,
            "rows": rows,
            "sections": sections,
            "area_map": area_map,
            "area_totals": area_totals,
            "crumbs": crumbs,
            "vendor_options": vendor_options,
            "software_tile": software_tile,
            "querystring": query.urlencode(),
        },
    )
