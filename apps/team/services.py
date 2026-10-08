"""Tablero del equipo (Bloque 7). Todo se calcula en lote: pocas consultas aunque haya decenas de personas."""

from collections import defaultdict

from django.db.models import Count, F

from apps.accounts.models import Person, PersonStatus
from apps.community.models import Note
from apps.credentials import expiry
from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.paths.models import (
    ExternalCourse,
    LearningPath,
    Level,
    Milestone,
    PathExtra,
    QuizQuestion,
    SharedItem,
)
from apps.progress.models import MilestoneCheck, QuizAnswer
from apps.progress.services import percent

from .models import SharedCheck

ATTRIBUTES = [
    ("MOD", "Modelado"),
    ("CAP", "Captura"),
    ("ANA", "Análisis"),
    ("DOC", "Documentación"),
    ("NOR", "Normativa"),
    ("COL", "Colaboración"),
]
MATRIX_PEOPLE_LIMIT = 80
RECENT = 8


def approved_people():
    return list(
        Person.objects.filter(status=PersonStatus.APPROVED, is_active=True).order_by(
            "display_name", "login"
        )
    )


def visible_paths(viewer):
    qs = LearningPath.objects.select_related("vendor")
    return list(qs if viewer.is_lead else qs.filter(is_published=True))


# --- avance por ruta y persona ------------------------------------------------------------------------------------


def path_percentages(people, paths):
    """{(person_id, path_id): % de avance}. Misma regla que las pantallas de cada mundo, calculada en lote."""
    ids = [p.pk for p in people]
    out = {(pid, path.pk): 0 for pid in ids for path in paths}
    structured = [p for p in paths if p.kind == LearningPath.Kind.STRUCTURED]
    external = [p for p in paths if p.kind == LearningPath.Kind.EXTERNAL_TRACK]

    if structured:
        total = defaultdict(int)
        for row in (
            Milestone.objects.filter(path__in=structured, retired=False)
            .values("path")
            .annotate(n=Count("id"))
        ):
            total[row["path"]] += row["n"]
        for row in (
            QuizQuestion.objects.filter(path__in=structured, retired=False)
            .values("path")
            .annotate(n=Count("id"))
        ):
            total[row["path"]] += row["n"]
        done = defaultdict(int)
        checks = (
            MilestoneCheck.objects.filter(
                person__in=ids, milestone__path__in=structured, milestone__retired=False
            )
            .values("person", "milestone__path")
            .annotate(n=Count("id"))
        )
        for row in checks:
            done[(row["person"], row["milestone__path"])] += row["n"]
        right = (
            QuizAnswer.objects.filter(
                person__in=ids,
                question__path__in=structured,
                question__retired=False,
                selected_index=F("question__answer_index"),
            )
            .values("person", "question__path")
            .annotate(n=Count("id"))
        )
        for row in right:
            done[(row["person"], row["question__path"])] += row["n"]
        for pid in ids:
            for path in structured:
                out[(pid, path.pk)] = percent(done[(pid, path.pk)], total[path.pk])

    if external:
        courses = list(
            ExternalCourse.objects.filter(path__in=external, retired=False).select_related("level")
        )
        verified = defaultdict(set)  # person_id -> resource_ids con credencial verificada
        rows = Credential.objects.filter(
            owner__in=ids, status=Credential.Status.VERIFIED, resource__isnull=False
        ).values_list("owner_id", "resource_id")
        for owner, resource in rows:
            verified[owner].add(resource)
        by_level = defaultdict(list)
        for c in courses:
            by_level[(c.path_id, c.level_id)].append(c)
        for path in external:
            levels = [(k, v) for k, v in by_level.items() if k[0] == path.pk]
            for pid in ids:
                req_total = req_done = 0
                for _, items in levels:
                    rule = items[0].level.completion_rule
                    have = [c for c in items if c.resource_id in verified[pid]]
                    if rule == Level.CompletionRule.ANY_ONE:
                        req_total += 1
                        req_done += int(bool(have))
                    else:
                        required = [c for c in items if c.is_required]
                        req_total += len(required)
                        req_done += sum(c.resource_id in verified[pid] for c in required)
                out[(pid, path.pk)] = percent(req_done, req_total)
    return out


def progress_table(viewer):
    people, paths = approved_people(), visible_paths(viewer)
    pct = path_percentages(people, paths)
    rows = [{"person": p, "cells": [pct[(p.pk, path.pk)] for path in paths]} for p in people]
    return {"paths": paths, "rows": rows}


# --- tablero -------------------------------------------------------------------------------------------------------


def recent_notes(limit=RECENT):
    return list(
        Note.objects.filter(
            is_deleted=False,
            is_hidden=False,
            parent__isnull=True,
            author__status=PersonStatus.APPROVED,
        ).select_related("author", "path")[:limit]
    )


def recent_credentials(viewer, limit=RECENT):
    return list(
        Credential.objects.filter(
            status=Credential.Status.VERIFIED, owner__status=PersonStatus.APPROVED
        )
        .filter(credential_services.visible_filter(viewer))
        .select_related("owner")
        .order_by("-reviewed_at", "-id")[:limit]
    )


def expiry_lists(viewer):
    visible = credential_services.visible_filter(viewer)
    return (
        list(expiry.expiring().filter(visible).order_by("expires_on")),
        list(expiry.expired().filter(visible).order_by("-expires_on")),
    )


# --- matriz de competencias ------------------------------------------------------------------------------------------


def matrix(viewer, attribute=""):
    """Personas × habilidades, a partir de credenciales verificadas (con la misma visibilidad del repositorio)."""
    from apps.catalog.models import Skill

    skills = Skill.objects.all().order_by("attribute", "name")
    if attribute in dict(ATTRIBUTES):
        skills = skills.filter(attribute=attribute)
    skills = list(skills)
    wanted = {s.pk for s in skills}
    people = approved_people()[:MATRIX_PEOPLE_LIMIT]
    counts = defaultdict(lambda: defaultdict(int))
    creds = (
        Credential.objects.filter(
            status=Credential.Status.VERIFIED, owner__in=[p.pk for p in people]
        )
        .filter(credential_services.visible_filter(viewer))
        .prefetch_related("skills", "resource__skills")
    )
    for cred in creds:
        found = {s.pk for s in cred.skills.all()}
        if cred.resource_id:
            found |= {s.pk for s in cred.resource.skills.all()}
        for pk in found & wanted:
            counts[cred.owner_id][pk] += 1
    rows = [{"person": p, "cells": [counts[p.pk][s.pk] for s in skills]} for p in people]
    totals = [sum(counts[p.pk][s.pk] for p in people) for s in skills]
    return {"skills": skills, "rows": rows, "totals": totals, "attribute": attribute}


# --- kit y plan ------------------------------------------------------------------------------------------------------------


def kit_and_plan(path):
    """Grupos del kit, fases del plan (con Gantt) y el estado de cada casilla compartida."""
    items = list(SharedItem.objects.filter(path=path).order_by("order", "key"))
    marks = {
        c.item_id: c
        for c in SharedCheck.objects.filter(item__path=path).select_related("checked_by")
    }
    groups = defaultdict(list)
    for item in items:
        groups[item.group_title].append({"item": item, "check": marks.get(item.pk)})
    kit_titles = [
        e.data["title"]
        for e in PathExtra.objects.filter(path=path, kind=PathExtra.Kind.TEAM_KIT).order_by("order")
    ]
    phases = []
    for e in PathExtra.objects.filter(path=path, kind=PathExtra.Kind.ROLLOUT_PHASE).order_by(
        "order"
    ):
        d = e.data
        rows = groups.get(d["title"], [])
        phases.append(
            {
                "title": d["title"],
                "label": d.get("label", ""),
                "start": d.get("start_week"),
                "end": d.get("end_week"),
                "recurring": d.get("recurring", False),
                "rows": rows,
                "done": sum(1 for r in rows if r["check"]),
                "total": len(rows),
            }
        )
    last = max([p["end"] for p in phases if p["end"] is not None] or [1])
    for p in phases:
        p["offset"] = (
            round(100 * (p["start"] or 0) / (last + 1), 2) if p["start"] is not None else 0
        )
        p["width"] = round(100 * ((p["end"] or last) - (p["start"] or 0) + 1) / (last + 1), 2)
        p["pct"] = percent(p["done"], p["total"])
    kit = [{"title": t, "rows": groups.get(t, [])} for t in kit_titles]
    return {"kit": kit, "phases": phases, "weeks": last + 1}


def set_shared(item, person, checked: bool):
    """Marca o desmarca una casilla compartida. Idempotente."""
    if person.status != PersonStatus.APPROVED:
        raise PermissionError("Tu cuenta aún no está aprobada.")
    if checked:
        SharedCheck.objects.get_or_create(item=item, defaults={"checked_by": person})
    else:
        SharedCheck.objects.filter(item=item).delete()
    return checked


def kit_paths(viewer):
    """Rutas que tienen kit o plan de implementación."""
    ids = SharedItem.objects.values_list("path_id", flat=True).distinct()
    return [p for p in visible_paths(viewer) if p.pk in set(ids)]
