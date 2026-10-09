from django.db.models import Case, IntegerField, Prefetch, Q, Value, When

from .models import Resource

ESSENTIAL = "Esencial"


def essential_ids():
    """Recursos marcados «Esencial» en su ruta (las etiquetas son JSON: SQLite no filtra dentro de listas)."""
    return [
        pk for pk, tags in Resource.objects.values_list("pk", "tags") if ESSENTIAL in (tags or [])
    ]


def published_paths_for(resource_ids):
    """{recurso: [rutas publicadas que lo usan]}: los borradores no se revelan en el catálogo."""
    from apps.paths.models import ExternalCourse, LevelResource

    out = {}
    links = LevelResource.objects.filter(
        resource_id__in=resource_ids, level__path__is_published=True
    ).select_related("level__path")
    courses = ExternalCourse.objects.filter(
        resource_id__in=resource_ids, path__is_published=True
    ).select_related("path")
    for rid, path in [(x.resource_id, x.level.path) for x in links] + [
        (c.resource_id, c.path) for c in courses
    ]:
        bucket = out.setdefault(rid, [])
        if path not in bucket:
            bucket.append(path)
    return out


def resource_queryset(
    *, platform="", kind="", free=False, cert=False, q="", product="", path="", essential=False
):
    qs = Resource.objects.select_related("platform").prefetch_related(
        Prefetch("skills"), "products"
    )
    if platform:
        qs = qs.filter(platform__slug=platform)
    if kind:
        qs = qs.filter(kind=kind)
    if free:
        qs = qs.filter(is_free=True)
    if cert:
        qs = qs.filter(Q(grants_completion_certificate=True) | Q(kind=Resource.Kind.EXAM))
    if product:
        qs = qs.filter(products__slug=product)
    if path:
        qs = qs.filter(
            Q(level_links__level__path__slug=path, level_links__level__path__is_published=True)
            | Q(external_courses__path__slug=path, external_courses__path__is_published=True)
        )
    ids = essential_ids()
    if essential:
        qs = qs.filter(pk__in=ids)
    if q:
        words = q.split()[:6]
        for word in words:  # cada palabra debe aparecer en algún campo: «revit familias» encuentra más que la frase exacta
            qs = qs.filter(
                Q(title__icontains=word)
                | Q(description__icontains=word)
                | Q(skills__name__icontains=word)
                | Q(products__name__icontains=word)
                | Q(platform__name__icontains=word)
            )
    # Primero lo esencial, luego lo oficial; dentro, por título.
    qs = qs.annotate(
        _essential=Case(
            When(pk__in=ids, then=Value(0)), default=Value(1), output_field=IntegerField()
        )
    ).order_by("_essential", "-is_official", "title")
    return qs.distinct()
