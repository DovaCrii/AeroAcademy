from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.gamification import game
from apps.paths.models import LearningPath

from . import services, software
from .models import Platform, Resource

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


GENERAL_PREVIEW = 6  # tarjetas de la sección «Conocimiento general» en la portada del catálogo
# garabato de la ruta según su mundo (img/doodles); «conocimiento» si el mundo no tiene uno propio
GENERAL_DOODLES = {"survey": "topografia", "architecture": "arquitectura", "civil": "civil"}


def _general_section(request, f, show_rows):
    """Sección «Conocimiento general · transversal»: las rutas generales y, sin filtros, sus recursos.

    Número fijo de consultas (rutas, etiquetas, recursos, rutas de cada recurso, avance): no crece con los datos.
    Devuelve None si no hay nada que mostrar o si el filtro activo es otro.
    """
    if not (show_rows or f["general"]):
        return None
    paths = services.general_paths()
    linked = services.resource_queryset(general=True)  # solo los que siguen en una ruta
    total = linked.count()
    if not paths and not total:
        return None
    pcts = game.path_percents(request.user, paths) if paths else {}
    for p in paths:
        p.pct = pcts.get(p.pk, 0)
        p.doodle = GENERAL_DOODLES.get(p.world, "conocimiento")
    items = []
    if show_rows and total:
        items = list(linked[:GENERAL_PREVIEW])
        in_paths = services.published_paths_for([r.pk for r in items])
        for r in items:
            r.in_paths = in_paths.get(r.pk, [])
    return {
        "paths": paths,
        "items": items,
        "total": total,
        "more": max(0, total - len(items)),
    }


def resources(request):
    """Catálogo: buscar por palabras, filtrar por ruta, tipo y plataforma; lo esencial va primero."""
    params = request.GET
    kind = params.get("kind", "")
    kind = kind if kind in Resource.Kind.values else ""
    paths = list(LearningPath.objects.filter(is_published=True).order_by("title"))
    path = params.get("ruta", "")
    path = path if path in {p.slug for p in paths} else ""
    f = {
        "platform": params.get("platform", ""),
        "kind": kind,
        "free": params.get("free") == "1",
        "cert": params.get("cert") == "1",
        "essential": params.get("esencial") == "1",
        "general": params.get("general") == "1",
        "path": path,
        "q": params.get("q", "").strip()[:100],
    }
    software_slug = params.get("software", "")
    software_slug = software_slug if software_slug in software.TILES else ""
    f["software"] = software_slug
    ids = None
    if software_slug:
        ids = software.resource_ids_for_software(services.resource_queryset(), software_slug)
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
    )
    filtered = any(v for v in f.values())
    rows = []
    show_rows = not filtered and params.get("todo") != "1" and "page" not in params
    if show_rows:  # sin filtros: filas por producto, como el home de Bentley Learn
        every = list(qs)
        rows = software.group_by_software(every)
        cards = [r for row in rows for r in row["items"]]
        in_paths = services.published_paths_for([r.pk for r in cards])
        for r in cards:
            r.in_paths = in_paths.get(r.pk, [])
    general = _general_section(request, f, show_rows)
    page = Paginator(qs, 24).get_page(params.get("page"))
    if not show_rows:
        in_paths = services.published_paths_for([r.pk for r in page])
        for r in page:
            r.in_paths = in_paths.get(r.pk, [])

    counts = dict(Resource.objects.values_list("kind").annotate(n=Count("pk")))
    kinds = [(value, label, counts.get(value, 0)) for value, label in KIND_GROUPS]
    kinds = [k for k in kinds if k[0] == "" or k[2]]

    query = params.copy()
    query.pop("page", None)
    base = params.copy()
    for key in ("page", "kind"):
        base.pop(key, None)
    route_base = params.copy()
    for key in ("page", "ruta"):
        route_base.pop(key, None)
    return render(
        request,
        "catalog/resources.html",
        {
            "page": page,
            "platforms": Platform.objects.filter(resources__isnull=False).distinct(),
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
            "general": general,
            "rows": rows,
            "sections": software.vendor_sections(rows),
            "software_tile": software.TILES.get(software_slug),
            "querystring": query.urlencode(),
            "kind_base": base.urlencode(),
            "route_base": route_base.urlencode(),
        },
    )
