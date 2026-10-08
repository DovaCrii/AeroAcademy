"""Datos vivos de la portada: misión sugerida, tablón del gremio y contadores (Bloque 12b)."""

import re
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PersonStatus
from apps.credentials import services as credential_services
from apps.credentials.models import WARNING_DAYS, Credential
from apps.gamification import game
from apps.gamification.models import PersonBadge, XPEvent
from apps.paths.models import ExternalCourse, LearningPath, Milestone
from apps.progress.models import MilestoneCheck

BOARD_DAYS = 7
BOARD_LIMIT = 8


def _plain(text):
    return re.sub(r"\*([^*]+)\*", r"\1", text).strip()


def _visible_paths(person):
    qs = LearningPath.objects.select_related("vendor")
    return qs if person.is_lead else qs.filter(is_published=True)


def _next_for_structured(person, path):
    checked = set(
        MilestoneCheck.objects.filter(person=person, milestone__path=path).values_list(
            "milestone_id", flat=True
        )
    )
    milestone = next(
        (
            m
            for m in Milestone.objects.filter(path=path, retired=False).select_related("level")
            if m.pk not in checked
        ),
        None,
    )
    if milestone is None:  # solo faltan preguntas del quiz
        return {
            "title": "Responde las preguntas de repaso",
            "detail": f"{path.title}",
            "url": reverse("paths:detail", args=[path.slug]),
        }
    return {
        "title": _plain(milestone.text),
        "detail": f"{path.title} · {milestone.level.short}",
        "url": reverse("paths:detail", args=[path.slug]) + f"?nivel={milestone.level.code}",
    }


def _next_for_external(person, path):
    states = credential_services.states_by_resource(person)
    required = list(
        ExternalCourse.objects.filter(path=path, is_required=True, retired=False)
        .select_related("resource")
        .order_by("level__order", "order")
    )
    missing = [c for c in required if states.get(c.resource_id, ("",))[0] != "verified"]
    waiting = {c.pk for c in missing if states.get(c.resource_id, ("",))[0] == "pending"}
    todo = [c for c in missing if c.pk not in waiting]
    if not todo:
        return None
    course = todo[0]
    return {
        "title": f"Registra tu certificado de «{course.resource.title}»",
        "detail": f"{path.title} · te faltan {len(missing)} cursos obligatorios",
        "url": reverse("credentials:register_course", args=[path.slug]) + f"?curso={course.key}",
    }


def suggested_mission(person):
    """La próxima acción útil: sigue la campaña con más avance que aún no termina; si no hay, la primera."""
    best = None
    for path in _visible_paths(person):
        pct = game.path_percent(person, path)
        if pct >= 100:
            continue
        key = (pct > 0, pct)
        if best is None or key > best[0]:
            best = (key, path, pct)
    if best is None:
        return None
    _, path, pct = best
    step = (
        _next_for_external(person, path)
        if path.kind == LearningPath.Kind.EXTERNAL_TRACK
        else _next_for_structured(person, path)
    )
    if step is None:
        return None
    return {**step, "pct": pct, "path": path}


def guild_board(person):
    """Logros de la última semana del equipo. Solo lo que cada persona dejó visible para el equipo."""
    since = timezone.now() - timedelta(days=BOARD_DAYS)
    rows = []
    badges = PersonBadge.objects.filter(
        earned_at__gte=since, person__status=PersonStatus.APPROVED
    ).select_related("person", "badge")
    for pb in badges:
        rows.append((pb.earned_at, f"{pb.person.name} ganó la insignia {pb.badge.name}"))
    for ev in XPEvent.objects.filter(
        created_at__gte=since, kind="path", person__status=PersonStatus.APPROVED
    ).select_related("person"):
        rows.append((ev.created_at, f"{ev.person.name} completó la campaña {ev.label}"))
    team_creds = Credential.objects.filter(
        status=Credential.Status.VERIFIED,
        visibility=Credential.Visibility.TEAM,
        reviewed_at__gte=since,
        owner__status=PersonStatus.APPROVED,
    ).select_related("owner")
    for cred in team_creds:
        rows.append(
            (cred.reviewed_at, f"{cred.owner.name} sumó un certificado: {cred.display_title}")
        )
    rows.sort(key=lambda r: r[0], reverse=True)
    weekly_xp = sum(
        XPEvent.objects.filter(created_at__gte=since, person__status=PersonStatus.APPROVED)
        .exclude(kind="streak")
        .values_list("points", flat=True)
    )
    return {
        "items": [{"when": w, "text": t} for w, t in rows[:BOARD_LIMIT]],
        "weekly_xp": weekly_xp,
        "days": BOARD_DAYS,
    }


def counters(person):
    today = timezone.localdate()
    out = {
        "expiring": Credential.objects.filter(
            owner=person,
            status=Credential.Status.VERIFIED,
            expires_on__isnull=False,
            expires_on__gte=today,
            expires_on__lte=today + timedelta(days=WARNING_DAYS),
        ).count(),
        "to_review": None,
    }
    if person.is_lead:
        out["to_review"] = Credential.objects.filter(status=Credential.Status.PENDING).count()
    return out
