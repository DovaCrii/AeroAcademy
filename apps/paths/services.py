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


# --- llamada a la acción por ruta ----------------------------------------------------------------------------------


def _pending_level_codes(person, path_ids):
    """pk de ruta → código del primer nivel pendiente. Mismo criterio que `progress.services.world_context`:
    un nivel está completo si tiene misiones o preguntas y todas están hechas; uno sin nada cuenta como pendiente.
    Cuatro consultas fijas, sin importar cuántas rutas."""
    from apps.progress.models import MilestoneCheck, QuizAnswer

    from .models import Level, Milestone, QuizQuestion

    levels = {}
    for pid, lid, code in (
        Level.objects.filter(path__in=path_ids)
        .order_by("order", "id")
        .values_list("path_id", "id", "code")
    ):
        levels.setdefault(pid, []).append((lid, code))
    checked = set(
        MilestoneCheck.objects.filter(person=person, milestone__path__in=path_ids).values_list(
            "milestone_id", flat=True
        )
    )
    answers = dict(
        QuizAnswer.objects.filter(person=person, question__path__in=path_ids).values_list(
            "question_id", "selected_index"
        )
    )
    todo, total = {}, {}  # nivel → pendientes / total
    for mid, lid in Milestone.objects.filter(path__in=path_ids, retired=False).values_list(
        "id", "level_id"
    ):
        total[lid] = total.get(lid, 0) + 1
        todo[lid] = todo.get(lid, 0) + (mid not in checked)
    for qid, lid, right in QuizQuestion.objects.filter(
        path__in=path_ids, retired=False
    ).values_list("id", "level_id", "answer_index"):
        total[lid] = total.get(lid, 0) + 1
        todo[lid] = todo.get(lid, 0) + (answers.get(qid) != right)
    out = {}
    for pid, items in levels.items():
        pending = next((code for lid, code in items if not total.get(lid) or todo.get(lid)), None)
        out[pid] = pending or items[0][1]
    return out


def route_ctas(person, paths, pcts=None):
    """pk de ruta → {state, label, url, pct}: el único botón primario de la tarjeta de una ruta.

    - 0 %: «Empezar la ruta →» al primer nivel; 1 a 99 %: «Continuar · N % →» al primer nivel pendiente;
    - 100 %: «Ver diploma ✦» si la ruta emite diploma (si no, «Repasar la ruta →»);
    - ruta de cursos externos: «Registrar mi primer curso →» mientras no haya ninguno.
    Las consultas son fijas: no crecen con el número de rutas.
    """
    from django.urls import reverse

    from apps.diplomas import services as diplomas
    from apps.gamification import game

    paths = list(paths)
    if not paths:
        return {}
    pcts = pcts if pcts is not None else game.path_percents(person, paths)
    codes = _pending_level_codes(person, [p.pk for p in paths])
    out = {}
    for p in paths:
        pct = pcts.get(p.pk, 0)
        base = reverse("paths:detail", args=[p.slug])
        external = p.kind == LearningPath.Kind.EXTERNAL_TRACK
        code = codes.get(p.pk)
        nivel = f"?nivel={code}#panel" if code and not external else "#panel"
        if pct >= 100:
            if diplomas.has_diploma(p):
                state, label, url = "done", "Ver diploma ✦", diplomas.url_for(p)
            else:
                state, label, url = "done", "Repasar la ruta →", base
        elif pct > 0:
            state, label, url = "continue", f"Continuar · {pct} % →", base + nivel
        elif external:
            state, label, url = "start", "Registrar mi primer curso →", base
        else:
            state, label, url = "start", "Empezar la ruta →", base + nivel
        out[p.pk] = {"state": state, "label": label, "url": url, "pct": pct}
    return out


def attach_ctas(person, paths, pcts=None):
    """Pone `p.cta` (y `p.pct`) en cada ruta para la tarjeta única; devuelve la lista. Consultas fijas."""
    paths = list(paths)
    ctas = route_ctas(person, paths, pcts)
    for p in paths:
        p.cta = ctas[p.pk]
        p.pct = p.cta["pct"]
    return paths


def cta_for(person, path):
    """Llamada a la acción de una sola ruta (ver `route_ctas`)."""
    return route_ctas(person, [path])[path.pk]
