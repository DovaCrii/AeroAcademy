from django.db.models import Prefetch, Q

from apps.catalog.models import Discipline, Product, Skill, Vendor

from .models import ExternalCourse, LearningPath, LevelResource


def visible_paths(person):
    """Las rutas sin publicar solo las ven los leads."""
    qs = LearningPath.objects.select_related("vendor", "platform")
    return qs if person.is_lead else qs.filter(is_published=True)


def path_listing(person, *, vendor="", product="", discipline="", skill=""):
    base = visible_paths(person)
    vendors = list(Vendor.objects.filter(paths__in=base).distinct())
    selected = next((v for v in vendors if v.slug == vendor), vendors[0] if vendors else None)

    paths = base.filter(vendor=selected) if selected else base.none()
    if product:
        paths = paths.filter(products__slug=product)
    if discipline:
        paths = paths.filter(disciplines__slug=discipline)
    if skill:
        paths = paths.filter(
            Q(levels__resources__skills__slug=skill)
            | Q(levels__external_courses__resource__skills__slug=skill)
        )
    paths = paths.distinct().prefetch_related("products", "disciplines")

    # Solo opciones que llevan a algo: un filtro sin rutas detrás es un camino sin nada.
    of_vendor = base.filter(vendor=selected) if selected else base.none()
    return {
        "vendors": vendors,
        "vendor": selected,
        "products": Product.objects.filter(paths__in=of_vendor)
        .distinct()
        .order_by("order", "name"),
        "disciplines": Discipline.objects.filter(paths__in=of_vendor).distinct(),
        "skills": Skill.objects.filter(
            Q(resources__levels__path__in=of_vendor)
            | Q(resources__external_courses__path__in=of_vendor)
        )
        .distinct()
        .order_by("name"),
        "paths": paths,
    }


def path_detail(path):
    """Capítulos con sus recursos, hitos, preguntas y cursos externos (sin lo retirado)."""
    levels = path.levels.prefetch_related(
        Prefetch(
            "level_resources",
            queryset=LevelResource.objects.select_related("resource").order_by("order"),
        ),
        "milestones",
        "quiz",
        Prefetch(
            "external_courses",
            queryset=ExternalCourse.objects.select_related("resource")
            .prefetch_related("resource__skills")
            .order_by("order"),
        ),
    ).order_by("order")
    result = []
    for level in levels:
        result.append(
            {
                "level": level,
                "resources": list(level.level_resources.all()),
                "milestones": [m for m in level.milestones.all() if not m.retired],
                "quiz": [q for q in level.quiz.all() if not q.retired],
                "courses": [c for c in level.external_courses.all() if not c.retired],
            }
        )
    return result
