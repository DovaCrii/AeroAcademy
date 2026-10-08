"""Motor de juego: XP, niveles, títulos e insignias (docs/GAMIFICACION.md).

Los demás módulos llaman a estas funciones de forma explícita (sin signals). Todo es idempotente:
`sync_*` reconcilian lo que *debería* existir con lo que existe, así marcar y desmarcar, verificar y
rechazar, o repetir una llamada nunca duplican XP ni dejan insignias de más.
"""

from datetime import date

from django.db import transaction
from django.db.models import Sum

from apps.credentials.models import Credential
from apps.paths.models import LearningPath, Milestone, QuizQuestion
from apps.progress.models import MilestoneCheck, QuizAnswer

from . import rules
from .models import Badge, PersonBadge, PlayerState, Title, XPEvent

POINTS = {
    "milestone": 10,
    "quiz": 5,
    "chapter": 25,
    "path": 150,
    "free_course_promoted": 30,
    "accepted_answer": 50,
    "note": 5,
}
CREDENTIAL_POINTS = {
    Credential.Kind.COMPLETION: 100,
    Credential.Kind.CERTIFICATION: 500,
    Credential.Kind.LICENSE: 300,
    Credential.Kind.INTERNAL: 50,
}
STREAK_STEP, STREAK_MAX = 20, 100


# --- niveles ----------------------------------------------------------------------------------------------


def xp_for_level(level: int) -> int:
    """XP total necesaria para llegar al nivel `level`: 50 × L × (L − 1)."""
    return 50 * level * (level - 1)


def level_for(xp: int) -> int:
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def total_xp(person) -> int:
    return XPEvent.objects.filter(person=person).aggregate(t=Sum("points"))["t"] or 0


def level_info(person, xp=None) -> dict:
    xp = total_xp(person) if xp is None else xp
    level = level_for(xp)
    floor, ceiling = xp_for_level(level), xp_for_level(level + 1)
    return {
        "xp": xp,
        "level": level,
        "into": xp - floor,
        "span": ceiling - floor,
        "to_next": ceiling - xp,
        "pct": int(100 * (xp - floor) / (ceiling - floor)),
    }


# --- XP ---------------------------------------------------------------------------------------------------


def award(person, source, kind, points=None, label="") -> bool:
    """Suma XP una sola vez por (persona, origen). Devuelve si fue nuevo."""
    points = POINTS.get(kind, 0) if points is None else points
    _, created = XPEvent.objects.get_or_create(
        person=person,
        source=source,
        defaults={"kind": kind, "points": points, "label": label[:200]},
    )
    return created


def revoke(person, source) -> bool:
    deleted, _ = XPEvent.objects.filter(person=person, source=source).delete()
    return bool(deleted)


def _reconcile(person, desired: dict, universe: set):
    """`desired`: origen → (tipo, puntos, detalle) que deben existir; `universe`: orígenes que gestiona quien llama."""
    existing = set(
        XPEvent.objects.filter(person=person, source__in=universe).values_list("source", flat=True)
    )
    for source, (kind, points, label) in desired.items():
        if source not in existing:
            award(person, source, kind, points, label)
    stale = existing - set(desired)
    if stale:
        XPEvent.objects.filter(person=person, source__in=stale).delete()


# --- progreso en rutas -------------------------------------------------------------------------------------


def _structured_state(person, path):
    """Misiones marcadas, capítulos completos y avance (%) de una ruta estructurada."""
    milestones = list(Milestone.objects.filter(path=path).values("id", "level_id", "retired"))
    questions = list(
        QuizQuestion.objects.filter(path=path, retired=False).values(
            "id", "level_id", "answer_index"
        )
    )
    checked = set(
        MilestoneCheck.objects.filter(person=person, milestone__path=path).values_list(
            "milestone_id", flat=True
        )
    )
    answers = dict(
        QuizAnswer.objects.filter(person=person, question__path=path).values_list(
            "question_id", "selected_index"
        )
    )
    per_level = {}
    for m in milestones:
        if m["retired"]:
            continue
        row = per_level.setdefault(m["level_id"], [0, 0])
        row[1] += 1
        row[0] += m["id"] in checked
    for q in questions:
        row = per_level.setdefault(q["level_id"], [0, 0])
        row[1] += 1
        row[0] += answers.get(q["id"]) == q["answer_index"]
    complete = {lvl for lvl, (done, total) in per_level.items() if total and done == total}
    done_all = sum(d for d, _ in per_level.values())
    total_all = sum(t for _, t in per_level.values())
    pct = int(100 * done_all / total_all + 0.5) if total_all else 0
    return {
        "milestones": milestones,
        "checked": checked,
        "complete_levels": complete,
        "levels": set(per_level),
        "pct": pct,
    }


def path_percent(person, path) -> int:
    if path.kind == LearningPath.Kind.EXTERNAL_TRACK:
        from apps.progress import external  # import tardío: external usa progress.services

        return external.external_context(person, path)["stats"]["pct"]
    return _structured_state(person, path)["pct"]


def sync_progress(person, path):
    """Reconcilia el XP de misiones, capítulos y campaña de una ruta con las marcas actuales."""
    if path.kind == LearningPath.Kind.EXTERNAL_TRACK:
        desired = {}
        if path_percent(person, path) >= 100:
            desired[f"path:{path.slug}"] = ("path", POINTS["path"], path.title)
        _reconcile(person, desired, {f"path:{path.slug}"})
        return
    state = _structured_state(person, path)
    desired, universe = {}, {f"path:{path.slug}"}
    for m in state["milestones"]:
        source = f"milestone:{m['id']}"
        universe.add(source)
        if m["id"] in state["checked"]:
            desired[source] = ("milestone", POINTS["milestone"], "")
    for level_id in state["levels"]:
        source = f"chapter:{level_id}"
        universe.add(source)
        if level_id in state["complete_levels"]:
            desired[source] = ("chapter", POINTS["chapter"], "")
    if state["levels"] and state["complete_levels"] == state["levels"]:
        desired[f"path:{path.slug}"] = ("path", POINTS["path"], path.title)
    _reconcile(person, desired, universe)


def award_quiz(person, question, correct: bool):
    """XP de pregunta: solo la primera vez que se acierta (no se revoca)."""
    if correct:
        award(person, f"quiz:{question.pk}", "quiz")


def on_milestone(person, milestone):
    sync_progress(person, milestone.path)
    return evaluate(person)


def on_quiz(person, question, correct):
    award_quiz(person, question, correct)
    sync_progress(person, question.path)
    return evaluate(person)


# --- credenciales -------------------------------------------------------------------------------------------


def sync_credentials(person):
    """XP de credenciales: solo las verificadas suman (D13); rechazar o devolver a revisión lo revoca."""
    rows = Credential.objects.filter(owner=person)
    desired = {}
    for cred in rows:
        if cred.is_verified and cred.kind in CREDENTIAL_POINTS:
            desired[f"credential:{cred.pk}"] = (
                "credential",
                CREDENTIAL_POINTS[cred.kind],
                cred.display_title,
            )
    universe = {f"credential:{pk}" for pk in rows.values_list("pk", flat=True)}
    # Orígenes de credenciales ya borradas: también se limpian.
    universe |= set(
        XPEvent.objects.filter(person=person, kind="credential").values_list("source", flat=True)
    )
    _reconcile(person, desired, universe)
    for path in LearningPath.objects.filter(kind=LearningPath.Kind.EXTERNAL_TRACK):
        sync_progress(person, path)


def on_credential_change(person):
    sync_credentials(person)
    return evaluate(person)


# --- insignias ----------------------------------------------------------------------------------------------


def unlocked_badges(person) -> set:
    return set(
        PersonBadge.objects.filter(person=person, badge__retired=False).values_list(
            "badge__slug", flat=True
        )
    )


def _streak_xp(person, facts):
    weeks = facts.active_weeks()
    here = rules.week_key(facts.today)
    if here in weeks:
        n = rules.streak_length(weeks, facts.today)
        key = f"{here[0]}-W{here[1]:02d}"
        award(person, f"streak:{key}", "streak", min(STREAK_MAX, STREAK_STEP * n), f"{n} semanas")


@transaction.atomic
def evaluate(person, today: date | None = None) -> list:
    """Recalcula las insignias de la persona. Devuelve las recién ganadas."""
    facts = rules.Facts(person, today)
    _streak_xp(person, facts)
    paths = {}

    def pct(slug):
        if slug not in paths:
            path = LearningPath.objects.filter(slug=slug).first()
            paths[slug] = path_percent(person, path) if path else 0
        return paths[slug]

    held = {pb.badge_id: pb for pb in PersonBadge.objects.filter(person=person)}
    gained = []
    for badge in Badge.objects.filter(retired=False):
        if badge.rule.get("type") == "manual":
            continue
        ok = rules.check(badge.rule, facts, pct)
        if ok and badge.pk not in held:
            gained.append(PersonBadge.objects.create(person=person, badge=badge))
        elif not ok and badge.pk in held:
            held[badge.pk].delete()
    return gained


def grant_manual(person, badge, by):
    """El moderador entrega una insignia `manual`."""
    if badge.rule.get("type") != "manual":
        raise ValueError("Esta insignia se gana sola.")
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede otorgar insignias.")
    return PersonBadge.objects.get_or_create(
        person=person, badge=badge, defaults={"granted_by": by}
    )


def refresh(person):
    """Reconcilia todo (útil tras importar datos o cambiar reglas)."""
    sync_credentials(person)
    for path in LearningPath.objects.filter(kind=LearningPath.Kind.STRUCTURED):
        sync_progress(person, path)
    return evaluate(person)


# --- títulos ------------------------------------------------------------------------------------------------


def available_titles(person, level=None):
    level = level_for(total_xp(person)) if level is None else level
    badges = unlocked_badges(person)
    out = []
    for title in Title.objects.filter(retired=False).select_related("badge"):
        if title.badge_id:
            if title.badge.slug in badges:
                out.append(title)
        elif title.min_level <= level and (
            not title.character_class or title.character_class == person.character_class
        ):
            out.append(title)
    return out


def displayed_title(person, level=None):
    """El título elegido si sigue disponible; si no, el más alto desbloqueado (el de clase gana a igual nivel)."""
    available = available_titles(person, level)
    chosen = getattr(person, "selected_title_id", None)
    for title in available:
        if title.pk == chosen:
            return title
    leveled = [t for t in available if not t.badge_id]
    leveled.sort(key=lambda t: (t.min_level, bool(t.character_class)), reverse=True)
    return leveled[0] if leveled else None


# --- celebraciones --------------------------------------------------------------------------------------------


def celebrations(person, level):
    """Insignias nuevas y subida de nivel aún no mostradas."""
    state, _ = PlayerState.objects.get_or_create(person=person)
    return {
        "badges": list(
            PersonBadge.objects.filter(person=person, seen=False).select_related("badge")
        ),
        "level_up": level if level > state.celebrated_level else None,
    }


def mark_seen(person, level):
    PersonBadge.objects.filter(person=person, seen=False).update(seen=True)
    PlayerState.objects.update_or_create(person=person, defaults={"celebrated_level": level})
