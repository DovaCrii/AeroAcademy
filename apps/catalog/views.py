from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

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
            "rows": rows,
            "software_tile": software.TILES.get(software_slug),
            "querystring": query.urlencode(),
            "kind_base": base.urlencode(),
            "route_base": route_base.urlencode(),
        },
    )
