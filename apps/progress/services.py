"""Avance por persona: misiones, quiz y meta de certificación.

Regla (docs/MODELO_DATOS.md): avance de un nivel = (misiones marcadas + preguntas correctas)
/ (misiones + preguntas). Se calcula, no se guarda. Lo retirado (D7) no cuenta.
"""

from collections import defaultdict

from django.utils import timezone

from apps.accounts.models import PersonStatus
from apps.paths import services as path_services
from apps.paths.models import PathExtra

from .models import MilestoneCheck, PathGoal, QuizAnswer


def percent(done: int, total: int) -> int:
    # Redondeo clásico (12,5 → 13); `round` de Python redondea la mitad al par.
    return int(100 * done / total + 0.5) if total else 0


# --- escritura ---


def set_milestone(person, milestone, checked: bool, *, credential=None) -> bool:
    """Marca o desmarca una misión. Idempotente: devuelve si cambió algo.

    Con `credential`, la marca queda respaldada por esa credencial verificada. Esa marca no se puede
    deshacer a mano: la evidencia manda (se quita sola si la credencial deja de estar verificada).
    """
    if milestone.retired:
        raise ValueError("La misión está retirada.")
    if checked:
        defaults = {"source": "credential", "credential": credential} if credential else {}
        _, created = MilestoneCheck.objects.get_or_create(
            person=person, milestone=milestone, defaults=defaults
        )
        return created
    existing = MilestoneCheck.objects.filter(person=person, milestone=milestone)
    if existing.filter(source="credential").exists():
        return False
    deleted, _ = existing.delete()
    return bool(deleted)


def answer_question(person, question, choice: int) -> QuizAnswer:
    """Guarda (o reemplaza) la respuesta de una persona a una pregunta."""
    if question.retired:
        raise ValueError("La pregunta está retirada.")
    if not 0 <= choice < len(question.options):
        raise ValueError("Opción fuera de rango.")
    answer, _ = QuizAnswer.objects.update_or_create(
        person=person,
        question=question,
        defaults={"selected_index": choice, "answered_at": timezone.now()},
    )
    return answer


def allowed_goals(path) -> list[str]:
    extras = PathExtra.objects.filter(path=path, kind=PathExtra.Kind.CERTIFICATION_GOAL)
    return [e.data["title"] for e in extras.order_by("order") if e.data.get("title")]


def set_goal(person, path, goal: str) -> None:
    goal = (goal or "").strip()
    if not goal:
        PathGoal.objects.filter(person=person, path=path).delete()
        return
    if goal not in allowed_goals(path):
        raise ValueError("Meta de certificación desconocida.")
    PathGoal.objects.update_or_create(
        person=person, path=path, defaults={"certification_goal": goal}
    )


# --- lectura ---


def initials(person) -> str:
    words = person.name.replace("@", " ").replace(".", " ").split()
    letters = "".join(w[0] for w in words[:2]) or person.login[:2]
    return letters.upper()


def _team_marks(path, chapters):
    """Dónde trabajó por última vez cada persona aprobada: su piso en el edificio."""
    last = {}  # person_id -> (momento, level_id, person)

    def consider(person, when, level_id):
        if person.status != PersonStatus.APPROVED:
            return
        current = last.get(person.pk)
        if current is None or when > current[0]:
            last[person.pk] = (when, level_id, person)

    checks = MilestoneCheck.objects.filter(milestone__path=path, milestone__retired=False)
    for c in checks.select_related("person", "milestone"):
        consider(c.person, c.checked_at, c.milestone.level_id)
    answers = QuizAnswer.objects.filter(question__path=path, question__retired=False)
    for a in answers.select_related("person", "question"):
        consider(a.person, a.answered_at, a.question.level_id)

    by_level = defaultdict(list)
    for _when, level_id, person in last.values():
        by_level[level_id].append(person)
    return by_level, len(last)


def _floors(chapters, marks, me_id):
    """Geometría del corte del edificio: un piso por nivel, el 0 abajo."""
    n = len(chapters)
    floor_h, top = 56, 64
    ground = top + n * floor_h + 4
    floors = []
    for i, ch in enumerate(chapters):
        y = top + (n - 1 - i) * floor_h + 4
        people = marks.get(ch["level"].id, [])
        floors.append(
            {
                "code": ch["level"].code,
                "short": ch["level"].short,
                "pct": ch["pct"],
                "complete": ch["complete"],
                "y": y,
                "mid": y + 31,
                "fill_w": round(400 * ch["pct"] / 100),
                "elev": f"+{i * 3.5:.2f}".replace(".", ","),
                "marks": [
                    {
                        "x": 564 + k * 30,
                        "initials": initials(p),
                        "name": p.name,
                        "me": p.pk == me_id,
                    }
                    for k, p in enumerate(people[:4])
                ],
                "extra": max(0, len(people) - 4),
                "extra_x": 564 + 4 * 30,
            }
        )
    return {"floors": floors, "ground": ground, "height": ground + 44, "top": top}


def world_context(person, path, level_code=None):
    """Todo lo que necesita la ruta interactiva de un mundo (docs/MUNDOS.md)."""
    chapters = path_services.path_detail(path)
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

    total_done = total_items = total_milestones = total_questions = 0
    for ch in chapters:
        ch["milestones"] = [{"obj": m, "checked": m.id in checked} for m in ch["milestones"]]
        quiz = []
        for q in ch["quiz"]:
            sel = answers.get(q.id)
            quiz.append(
                {
                    "obj": q,
                    "selected": sel,
                    "answered": sel is not None,
                    "correct": sel == q.answer_index,
                    "options": list(enumerate(q.options)),
                }
            )
        ch["quiz"] = quiz
        done = sum(m["checked"] for m in ch["milestones"]) + sum(q["correct"] for q in quiz)
        total = len(ch["milestones"]) + len(quiz)
        ch.update(
            done=done, total=total, pct=percent(done, total), complete=bool(total) and done == total
        )
        total_done += done
        total_items += total
        total_milestones += len(ch["milestones"])
        total_questions += len(quiz)

    codes = [ch["level"].code for ch in chapters]
    if level_code not in codes:
        pending = next((ch for ch in chapters if not ch["complete"]), None)
        level_code = (pending or chapters[0])["level"].code if chapters else None
    index = codes.index(level_code) if level_code else 0
    current = chapters[index] if chapters else None

    marks, participants = _team_marks(path, chapters)
    goal = PathGoal.objects.filter(person=person, path=path).first()
    extras = list(path.extras.filter(kind__in=[PathExtra.Kind.INTRO, PathExtra.Kind.FLOW]))
    intro = next((e.data for e in extras if e.kind == PathExtra.Kind.INTRO), {})
    flow = [e.data for e in extras if e.kind == PathExtra.Kind.FLOW]
    program = [part.strip() for part in path.program.split("·")]
    return {
        "path": path,
        "program_code": program[0] if len(program) > 1 else "",
        "program_title": program[-1] or path.title,
        "intro": intro,
        "flow": flow,
        "chapters": chapters,
        "current": current,
        "prev_code": codes[index - 1] if index > 0 else None,
        "next_code": codes[index + 1] if index + 1 < len(codes) else None,
        "building": _floors(chapters, marks, person.pk),
        "stats": {
            "levels_done": sum(ch["complete"] for ch in chapters),
            "levels_total": len(chapters),
            "participants": participants,
            "pct": percent(total_done, total_items),
            "milestones": total_milestones,
            "questions": total_questions,
        },
        "goals": allowed_goals(path),
        "goal": goal.certification_goal if goal else "",
        "products": path.products.all(),
        "disciplines": path.disciplines.all(),
    }
