from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.paths import services as path_services
from apps.paths.models import LearningPath

from . import services, software
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


GENERAL_PREVIEW = 6  # tarjetas de la sección «Conocimiento general» en la portada del catálogo


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
    paths = (
        path_services.attach_ctas(request.user, paths) if paths else []
    )  # avance y botón: consultas fijas
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
    f = {
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
        discipline=discipline,
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

    platforms = list(Platform.objects.filter(resources__isnull=False).distinct())
    counts = dict(Resource.objects.values_list("kind").annotate(n=Count("pk")))
    kinds = [(value, label, counts.get(value, 0)) for value, label in KIND_GROUPS]
    kinds = [k for k in kinds if k[0] == "" or k[2]]

    query = params.copy()
    query.pop("page", None)
    kind_label = dict(KIND_GROUPS).get(kind, "")
    software_tile = software.TILES.get(software_slug)
    labels = {
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
            "general": general,
            "rows": rows,
            "sections": software.vendor_sections(rows),
            "software_tile": software_tile,
            "querystring": query.urlencode(),
        },
    )
