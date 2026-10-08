"""Carga de rutas desde seed/rutas/*.json (idempotente).

Reglas (D7): las `key` nunca se renumeran.
Lo que desaparece del JSON no se borra: se marca `retired`.
"""

from apps.catalog.models import Discipline, Platform, Product, Resource, Skill, Vendor, World
from apps.catalog.seeding import SeedError, _dupes

from .models import (
    ExternalCourse,
    LearningPath,
    Level,
    LevelResource,
    Milestone,
    PathExtra,
    QuizQuestion,
    SharedItem,
)

# etiqueta del prototipo → tipo de recurso
TAG_KIND = {
    "Course": "course",
    "Module": "module",
    "Tutorial": "tutorial",
    "Exercise": "tutorial",
    "cert": "exam",
    "Collection": "collection",
    "Catalog": "collection",
    "Blog": "article",
}


def _all_level_resources(data):
    for level in data.get("levels", []):
        yield from level.get("resources", [])


def validate_route(data, name="ruta"):
    errors = []

    def err(msg):
        errors.append(f"{name}: {msg}")

    for field in ("slug", "title", "platform", "kind", "vendor", "world", "levels"):
        if not data.get(field):
            err(f"falta «{field}»")
    if errors:
        return errors

    if data["kind"] not in {k.value for k in LearningPath.Kind}:
        err(f"tipo inválido «{data['kind']}»")
    if data["world"] not in {w.value for w in World}:
        err(f"mundo inválido «{data['world']}»")
    if not Vendor.objects.filter(slug=data["vendor"]).exists():
        err(f"vendor desconocido «{data['vendor']}»")
    if not Platform.objects.filter(slug=data["platform"]).exists():
        err(f"plataforma desconocida «{data['platform']}»")
    for label, model, slugs in (
        ("producto", Product, data.get("products", [])),
        ("disciplina", Discipline, data.get("disciplines", [])),
    ):
        known = set(model.objects.filter(slug__in=slugs).values_list("slug", flat=True))
        for slug in slugs:
            if slug not in known:
                err(f"{label} desconocido «{slug}»")

    levels = data["levels"]
    for code in _dupes(level.get("code") for level in levels):
        err(f"código de capítulo duplicado «{code}»")

    milestones = [m for level in levels for m in level.get("milestones", [])]
    quiz = [q for level in levels for q in level.get("quiz", [])]
    courses = [c for level in levels for c in level.get("external_courses", [])]
    for label, items in (("hito", milestones), ("pregunta", quiz), ("curso externo", courses)):
        for key in _dupes(i.get("key") for i in items):
            err(f"{label} con clave duplicada «{key}»")
        for item in items:
            if not item.get("key"):
                err(f"{label} sin clave")

    titles = {r["title"] for r in _all_level_resources(data)}
    for m in milestones:
        wanted = m.get("completed_by_resource")
        if wanted and wanted not in titles:
            err(f"hito {m['key']}: completed_by_resource «{wanted}» no está en los recursos")
    for q in quiz:
        options = q.get("options", [])
        if not isinstance(q.get("answer"), int) or not 0 <= q["answer"] < len(options):
            err(f"pregunta {q['key']}: «answer» fuera de rango")

    skill_slugs = {s for c in courses for s in c.get("skills", [])}
    known_skills = set(Skill.objects.filter(slug__in=skill_slugs).values_list("slug", flat=True))
    for slug in sorted(skill_slugs - known_skills):
        err(f"habilidad desconocida «{slug}»")
    rewards = {r.value for r in ExternalCourse.Reward}
    for c in courses:
        if c.get("reward") not in rewards:
            err(f"curso {c.get('key')}: reward inválido «{c.get('reward')}»")
        if not c.get("title"):
            err(f"curso {c.get('key')}: sin título")
    if data["kind"] == LearningPath.Kind.EXTERNAL_TRACK and not courses:
        err("una ruta externa necesita al menos un curso externo")
    return errors


def _kind_from_tags(tags):
    for tag in tags:
        if tag in TAG_KIND:
            return TAG_KIND[tag]
    return "guide"


def _upsert_resource(platform, item, *, certificate=False, official=None, kind=None):
    tags = item.get("tags", [])
    resource_kind = kind or item.get("kind") or _kind_from_tags(tags)
    resource, _ = Resource.objects.update_or_create(
        platform=platform,
        title=item["title"],
        defaults={
            "url": item.get("url", ""),
            "kind": resource_kind,
            "description": item.get("description", ""),
            "duration_text": item.get("duration_text", ""),
            "tags": tags,
            "is_official": "Oficial" in tags if official is None else official,
            "is_free": resource_kind != "exam",
            "grants_completion_certificate": certificate or "Certificate of completion" in tags,
            "verify_url": bool(item.get("verify_url", False)),
        },
    )
    return resource


def load_route(data, name="ruta"):
    errors = validate_route(data, name)
    if errors:
        raise SeedError(errors)

    platform = Platform.objects.get(slug=data["platform"])
    path, _ = LearningPath.objects.update_or_create(
        slug=data["slug"],
        defaults={
            "title": data["title"],
            "program": data.get("program", ""),
            "platform": platform,
            "vendor": Vendor.objects.get(slug=data["vendor"]),
            "kind": data["kind"],
            "world": data["world"],
            "description": data.get("description", ""),
            "allow_free_courses": data.get("allow_free_courses", False),
        },
    )
    path.products.set(Product.objects.filter(slug__in=data.get("products", [])))
    path.disciplines.set(Discipline.objects.filter(slug__in=data.get("disciplines", [])))

    milestone_keys, quiz_keys, course_keys = [], [], []
    for level_data in data["levels"]:
        level, _ = Level.objects.update_or_create(
            path=path,
            code=level_data["code"],
            defaults={
                "order": level_data.get("order", 0),
                "short": level_data.get("short", level_data["code"]),
                "title": level_data["title"],
                "estimated_hours": level_data.get("estimated_hours", ""),
                "audience": level_data.get("audience", ""),
                "goal": level_data.get("goal", ""),
                "mastery_signals": level_data.get("mastery_signals", []),
                "completion_rule": data_completion_rule(level_data),
                "is_free_courses": bool(level_data.get("free_courses_land_here", False)),
            },
        )

        kept = []
        for r_order, item in enumerate(level_data.get("resources", [])):
            resource = _upsert_resource(platform, item)
            LevelResource.objects.update_or_create(
                level=level,
                resource=resource,
                defaults={"order": item.get("order", r_order), "note": item.get("description", "")},
            )
            kept.append(resource.pk)
        LevelResource.objects.filter(level=level).exclude(resource_id__in=kept).delete()

        for order, m in enumerate(level_data.get("milestones", [])):
            linked = None
            if m.get("completed_by_resource"):
                linked = Resource.objects.get(platform=platform, title=m["completed_by_resource"])
            Milestone.objects.update_or_create(
                path=path,
                key=m["key"],
                defaults={
                    "level": level,
                    "order": order,
                    "text": m["text"],
                    "completed_by_resource": linked,
                    "retired": False,
                },
            )
            milestone_keys.append(m["key"])

        for order, q in enumerate(level_data.get("quiz", [])):
            QuizQuestion.objects.update_or_create(
                path=path,
                key=q["key"],
                defaults={
                    "level": level,
                    "order": order,
                    "question": q["question"],
                    "options": q["options"],
                    "answer_index": q["answer"],
                    "explanation": q.get("explanation", ""),
                    "retired": False,
                },
            )
            quiz_keys.append(q["key"])

        for order, c in enumerate(level_data.get("external_courses", [])):
            resource = _upsert_resource(platform, c, certificate=True, official=True)
            if c.get("skills"):
                resource.skills.set(Skill.objects.filter(slug__in=c["skills"]))
            course, _ = ExternalCourse.objects.update_or_create(
                path=path,
                key=c["key"],
                defaults={
                    "level": level,
                    "order": c.get("order", order),
                    "resource": resource,
                    "reward": c["reward"],
                    "is_required": c.get("is_required", True),
                    "contains": c.get("contains", []),
                    "retired": False,
                },
            )
            course.disciplines.set(Discipline.objects.filter(slug__in=c.get("disciplines", [])))
            course_keys.append(c["key"])

    # D7: lo que ya no está en el JSON se retira, no se borra (puede haber avance guardado).
    Milestone.objects.filter(path=path).exclude(key__in=milestone_keys).update(retired=True)
    QuizQuestion.objects.filter(path=path).exclude(key__in=quiz_keys).update(retired=True)
    ExternalCourse.objects.filter(path=path).exclude(key__in=course_keys).update(retired=True)

    _load_extras(path, data)
    return path


def data_completion_rule(level_data):
    rule = level_data.get("completion_rule", "all_required")
    return "any_one" if rule == "any_one" else "all_required"


def _load_extras(path, data):
    PathExtra.objects.filter(path=path).delete()
    extras = []

    def add(kind, items):
        extras.extend(
            PathExtra(path=path, kind=kind, order=i, data=item) for i, item in enumerate(items)
        )

    add(PathExtra.Kind.CAPABILITY, data.get("capabilities", []))
    add(PathExtra.Kind.GLOSSARY, data.get("glossary", []))
    add(PathExtra.Kind.TEAM_KIT, data.get("team_kit", []))
    add(PathExtra.Kind.ROLLOUT_PHASE, data.get("rollout_phases", []))
    add(
        PathExtra.Kind.CERTIFICATION_GOAL,
        [{"title": t} for t in data.get("certification_goals", [])],
    )
    add(PathExtra.Kind.CERTIFICATION_STEP, data.get("certification_ladder", []))
    PathExtra.objects.bulk_create(extras)

    for group in data.get("team_kit", []):
        for i, item in enumerate(group.get("items", [])):
            _shared(path, item, group["title"], None, None, i)
    for phase in data.get("rollout_phases", []):
        for i, item in enumerate(phase.get("items", [])):
            _shared(path, item, phase["title"], phase.get("start_week"), phase.get("end_week"), i)


def _shared(path, item, group_title, start, end, order):
    SharedItem.objects.update_or_create(
        path=path,
        key=item["key"],
        defaults={
            "text": item["text"],
            "group_title": group_title,
            "start_week": start,
            "end_week": end,
            "order": order,
        },
    )
