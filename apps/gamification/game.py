"""Motor de juego: XP, niveles, títulos e insignias (docs/GAMIFICACION.md).

Los demás módulos llaman a estas funciones de forma explícita (sin signals). Todo es idempotente:
`sync_*` reconcilian lo que *debería* existir con lo que existe, así marcar y desmarcar, verificar y
rechazar, o repetir una llamada nunca duplican XP ni dejan insignias de más.
"""

from datetime import date

from django.db import transaction
from django.db.models import Sum

from apps.credentials.models import Credential
from apps.notifications import services as notifications
from apps.paths.models import ExternalCourse, LearningPath, Level, Milestone, QuizQuestion
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


def resource_xp(resource) -> int:
    """XP que suma un curso cuando su certificado queda verificado (0 si no entrega certificado).
    Un examen cuenta como certificación; un curso con certificado de término, como curso (D13)."""
    from apps.catalog.models import Resource  # import tardío: catalog no depende del juego

    if resource.kind == Resource.Kind.EXAM:
        return CREDENTIAL_POINTS[Credential.Kind.CERTIFICATION]
    if resource.grants_completion_certificate:
        return CREDENTIAL_POINTS[Credential.Kind.COMPLETION]
    return 0


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
        else:  # el valor puede haber cambiado (p. ej. el tipo de la credencial)
            XPEvent.objects.filter(person=person, source=source).exclude(
                points=points, kind=kind
            ).update(points=points, kind=kind, label=label[:200])
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


def _percent(done: int, total: int) -> int:
    # Redondeo clásico (12,5 → 13), igual que `progress.services.percent`.
    return int(100 * done / total + 0.5) if total else 0


def path_percents(person, paths) -> dict:
    """pk de ruta → avance (%) de la persona, para muchas rutas a la vez.

    Cuesta un número fijo de consultas (4 para las estructuradas, 2 más para las externas) sin importar
    cuántas rutas, capítulos, misiones o cursos haya: trae todo junto y calcula en Python.
    Debe coincidir con `_structured_state(...)["pct"]` y con `external_context(...)["stats"]["pct"]`.
    """
    paths = list(paths)
    out = {p.pk: 0 for p in paths}
    structured = [p.pk for p in paths if p.kind != LearningPath.Kind.EXTERNAL_TRACK]
    external = [p.pk for p in paths if p.kind == LearningPath.Kind.EXTERNAL_TRACK]

    if structured:
        checked = set(
            MilestoneCheck.objects.filter(
                person=person, milestone__path__in=structured
            ).values_list("milestone_id", flat=True)
        )
        answers = dict(
            QuizAnswer.objects.filter(person=person, question__path__in=structured).values_list(
                "question_id", "selected_index"
            )
        )
        totals = {pk: [0, 0] for pk in structured}  # ruta → [hechas, total]
        for mid, pid in Milestone.objects.filter(path__in=structured, retired=False).values_list(
            "id", "path_id"
        ):
            totals[pid][1] += 1
            totals[pid][0] += mid in checked
        for qid, pid, answer in QuizQuestion.objects.filter(
            path__in=structured, retired=False
        ).values_list("id", "path_id", "answer_index"):
            totals[pid][1] += 1
            totals[pid][0] += answers.get(qid) == answer
        for pid, (done, total) in totals.items():
            out[pid] = _percent(done, total)

    if external:
        from apps.credentials import services as credential_services

        states = credential_services.states_by_resource(person)
        verified = Credential.Status.VERIFIED
        by_level = {}  # (ruta, capítulo) → (regla, [(obligatorio, verificado)])
        for pid, lid, rule, resource_id, required in ExternalCourse.objects.filter(
            path__in=external, retired=False
        ).values_list(
            "path_id", "level_id", "level__completion_rule", "resource_id", "is_required"
        ):
            ok = states.get(resource_id, ("",))[0] == verified
            by_level.setdefault((pid, lid), (rule, []))[1].append((required, ok))
        totals = {pk: [0, 0] for pk in external}
        for (pid, _lid), (rule, courses) in by_level.items():
            if rule == Level.CompletionRule.ANY_ONE:
                totals[pid][1] += 1
                totals[pid][0] += any(ok for _, ok in courses)
            else:
                required = [ok for req, ok in courses if req]
                totals[pid][1] += len(required)
                totals[pid][0] += sum(required)
        for pid, (done, total) in totals.items():
            out[pid] = _percent(done, total)
    return out


def path_percent(person, path) -> int:
    return path_percents(person, [path])[path.pk]


def structured_status(person, path) -> dict:
    """Avance de una ruta estructurada por capítulo (código): misiones y preguntas hechas y totales.

    Cinco consultas fijas. El `pct` coincide con `path_percents` (mismo redondeo; lo retirado no cuenta).
    """
    codes = dict(Level.objects.filter(path=path).values_list("id", "code"))
    rows = {c: {"done": 0, "total": 0, "quiz_done": 0, "quiz_total": 0} for c in codes.values()}
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
    for mid, lid in Milestone.objects.filter(path=path, retired=False).values_list(
        "id", "level_id"
    ):
        row = rows[codes[lid]]
        row["total"] += 1
        row["done"] += mid in checked
    for qid, lid, answer in QuizQuestion.objects.filter(path=path, retired=False).values_list(
        "id", "level_id", "answer_index"
    ):
        row = rows[codes[lid]]
        row["total"] += 1
        row["quiz_total"] += 1
        ok = answers.get(qid) == answer
        row["done"] += ok
        row["quiz_done"] += ok
    done = sum(r["done"] for r in rows.values())
    total = sum(r["total"] for r in rows.values())
    return {"levels": rows, "pct": _percent(done, total)}


class PathContext:
    """Avance de una persona en las rutas que piden las reglas, con caché (una ruta se consulta una sola vez)."""

    def __init__(self, person):
        self.person = person
        self._status = {}
        self._general = None

    def status(self, slug) -> dict:
        if slug not in self._status:
            path = LearningPath.objects.filter(slug=slug).first()
            if path is None:
                status = {"levels": {}, "pct": 0}
            elif path.kind == LearningPath.Kind.EXTERNAL_TRACK:
                status = {"levels": {}, "pct": path_percent(self.person, path)}
            else:
                status = structured_status(self.person, path)
            self._status[slug] = status
        return self._status[slug]

    def pct(self, slug) -> int:
        return self.status(slug)["pct"]

    def general(self) -> list:
        """Slugs de las rutas de conocimiento general vigentes (datos: una ruta nueva cuenta sola)."""
        if self._general is None:
            from apps.catalog import services as catalog

            self._general = list(
                catalog.general_paths_queryset().order_by("title").values_list("slug", flat=True)
            )
        return self._general


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


def prefetch_badges(people):
    """Una sola consulta para listas de personas (evita una por tarjeta)."""
    by_person = {p.pk: set() for p in people}
    rows = PersonBadge.objects.filter(person__in=by_person, badge__retired=False).values_list(
        "person_id", "badge__slug"
    )
    for pid, slug in rows:
        by_person[pid].add(slug)
    for p in people:
        p._badge_slugs = by_person[p.pk]


def unlocked_badges(person) -> set:
    cached = getattr(person, "_badge_slugs", None)
    if cached is not None:
        return set(cached)
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
    ctx = PathContext(person)
    held = {pb.badge_id: pb for pb in PersonBadge.objects.filter(person=person)}
    gained = []
    for badge in Badge.objects.filter(retired=False):
        if badge.rule.get("type") == "manual":
            continue
        ok = rules.check(badge.rule, facts, ctx.pct, ctx)
        if ok and badge.pk not in held:
            gained.append(PersonBadge.objects.create(person=person, badge=badge))
        elif not ok and badge.pk in held:
            held[badge.pk].delete()
    for pb in gained:
        notifications.notify(
            person,
            "badge",
            f"Ganaste la insignia {pb.badge.name}",
            pb.badge.description,
            url="/perfil/",
            key=f"badge:{pb.badge.slug}",
        )
    level = level_for(total_xp(person))
    if level > 1:
        notifications.notify(
            person,
            "level_up",
            f"¡Subiste al nivel {level}!",
            url="/perfil/",
            key=f"level:{level}",
        )
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
        if title.badge_id:  # lo da una insignia; si además trae carrera, solo esa carrera lo ve
            if title.badge.slug in badges and (
                not title.character_class or title.character_class == person.character_class
            ):
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


def mark_seen(person, level=None, badge_ids=None):
    """Marca como vistas las insignias indicadas (todas si no se indican) y el nivel celebrado."""
    badges = PersonBadge.objects.filter(person=person, seen=False)
    if badge_ids is not None:
        badges = badges.filter(pk__in=badge_ids)
    badges.update(seen=True)
    if level is not None:
        PlayerState.objects.update_or_create(person=person, defaults={"celebrated_level": level})
