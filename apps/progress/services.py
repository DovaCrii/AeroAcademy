"""Avance por persona: misiones, quiz y meta de certificación.

Regla (docs/MODELO_DATOS.md): avance de un nivel = (misiones marcadas + preguntas correctas)
/ (misiones + preguntas). Se calcula, no se guarda. Lo retirado (D7) no cuenta.
"""

import math
from collections import defaultdict

from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PersonStatus
from apps.catalog import figure_layout, figures, guides
from apps.catalog.figure_layout import clip
from apps.gamification import game
from apps.paths import services as path_services
from apps.paths.models import PathExtra

from .models import MilestoneCheck, PathGoal, QuizAnswer


def percent(done: int, total: int) -> int:
    # Redondeo clásico (12,5 → 13); `round` de Python redondea la mitad al par.
    return int(100 * done / total + 0.5) if total else 0


# --- escritura ---


def _diploma(person, path):
    """Si la ruta es nuestra y quedó al 100 %, emite el diploma interno (idempotente)."""
    from apps.diplomas import (
        services as diplomas,
    )  # import tardío: diplomas usa credentials, que usa progress

    diplomas.on_progress(person, path)


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
        if created and credential is None:
            game.on_milestone(
                person, milestone
            )  # con credencial, la sincronía la hace quien verifica
            _diploma(person, milestone.path)
        return created
    existing = MilestoneCheck.objects.filter(person=person, milestone=milestone)
    if existing.filter(source="credential").exists():
        return False
    deleted, _ = existing.delete()
    if deleted:
        game.on_milestone(person, milestone)
        _diploma(person, milestone.path)  # no quita el diploma ya emitido
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
    game.on_quiz(person, question, choice == question.answer_index)
    _diploma(person, question.path)
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


FLOOR_LABEL_MAX = 38  # el nombre ocupa de x = 178 a ~460; el porcentaje empieza en 508


def _floors(chapters, marks, me_id, step=None):
    """Geometría del corte del edificio: un piso por nivel, el 0 abajo. `step(i)` da el rótulo de la cota del piso."""
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
                "label": clip(ch["level"].short, FLOOR_LABEL_MAX),
                "pct": ch["pct"],
                "complete": ch["complete"],
                "y": y,
                "mid": y + 31,
                "fill_w": round(400 * ch["pct"] / 100),
                "elev": step(i) if step else f"+{i * 3.5:.2f}".replace(".", ","),
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


# Cajas aproximadas del plan de vuelo (viewBox 760 × 330): el dron va al lado opuesto de la etiqueta.
DRONE_HALF = (13, 9)  # media anchura y media altura del dron
LABEL_CHAR_W, LABEL_H = 7, 14  # una letra ≈ 7 px; una línea de rótulo ≈ 14 px
WP_LABEL_MAX = 16


def label_box(p):
    """Caja (x0, y0, x1, y1) que ocupan el nombre y el porcentaje de un waypoint."""
    w = max(len(p["label"]), 6) * LABEL_CHAR_W / 2
    if p["above"]:
        y0, y1 = p["y"] - 46 - LABEL_H, p["y"] - 32
    else:
        y0, y1 = p["y"] + 42 - LABEL_H, p["y"] + 56
    return (p["x"] - w, y0, p["x"] + w, y1)


def drone_box(p):
    """Caja (x0, y0, x1, y1) del dron de un waypoint (solo hay dron en el waypoint `here`)."""
    cx, cy = p["x"] + p["drone_dx"], p["y"] + p["drone_dy"]
    return (cx - DRONE_HALF[0], cy - DRONE_HALF[1], cx + DRONE_HALF[0], cy + DRONE_HALF[1])


def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _drone_offset(p, points, width, height):
    """Desplazamiento (dx, dy) del dron: al lado opuesto de su etiqueta y sin tapar la de ningún vecino.

    Prueba primero ese lado sin moverse y luego corrido en x (±30, ±45); el primer hueco que cabe en el dibujo gana.
    """
    opposite = 34 if p["above"] else -30
    labels = [label_box(q) for q in points]
    for dx in (0, 30, -30, 45, -45):
        box = drone_box({**p, "drone_dx": dx, "drone_dy": opposite})
        inside = box[0] >= 0 and box[2] <= width and box[1] >= 0 and box[3] <= height
        if inside and not any(boxes_overlap(box, lb) for lb in labels):
            return dx, opposite
    return 0, opposite


def _waypoints(chapters, marks, me_id):
    """Plan de vuelo del mundo `aero`: un waypoint por nivel sobre una ruta que sube; el dron espera en el primero
    sin completar. Cada waypoint lleva su anillo de avance (circunferencia r = 18 → 113,1)."""
    n = len(chapters)
    width, height, left, right, base, top = 760, 330, 70, 690, 262, 72
    points = []
    here = next((i for i, ch in enumerate(chapters) if not ch["complete"]), None)
    # Con muchos waypoints, el rótulo se acorta para no invadir el hueco del dron en el lado opuesto.
    spacing = (right - left) / max(n - 1, 1)
    label_max = max(6, min(WP_LABEL_MAX, int(2 * (spacing - DRONE_HALF[0] - 2) / LABEL_CHAR_W)))
    for i, ch in enumerate(chapters):
        t = i / (n - 1) if n > 1 else 0.5
        x = round(left + (right - left) * t)
        y = round(base - (base - top) * t + 22 * math.sin(i * 1.7))
        people = marks.get(ch["level"].id, [])
        point = {
            "code": ch["level"].code,
            "short": ch["level"].short,
            "label": clip(ch["level"].short, label_max),
            "pct": ch["pct"],
            "complete": ch["complete"],
            "x": x,
            "y": y,
            "above": i % 2 == 0,
            "ring": round(113.1 * ch["pct"] / 100, 1),
            "here": i == here,
            "drone_dx": 0,
            "drone_dy": 0,
            "marks": [
                {
                    "dx": 24 + k * 22,
                    "initials": initials(p),
                    "name": p.name,
                    "me": p.pk == me_id,
                }
                for k, p in enumerate(people[:3])
            ],
            "extra": max(0, len(people) - 3),
        }
        points.append(point)
    for point in points:
        if point["here"]:
            point["drone_dx"], point["drone_dy"] = _drone_offset(point, points, width, height)
    segments = [
        {"x1": a["x"], "y1": a["y"], "x2": b["x"], "y2": b["y"], "done": chapters[i]["complete"]}
        for i, (a, b) in enumerate(zip(points, points[1:], strict=False))
    ]
    return {"width": width, "height": height, "points": points, "segments": segments}


def _stations(chapters, marks, me_id):
    """Estaciones de las figuras: un nivel cada una, con el avance real y las personas del equipo que están ahí."""
    out = []
    for ch in chapters:
        people = marks.get(ch["level"].id, [])
        out.append(
            figure_layout.station(
                ch["level"].code,
                ch["level"].short,
                ch["pct"],
                ch["complete"],
                fid=ch["level"].code,
                say=f"{ch['pct']} % completo",
                noun="Nivel",
                marks=[
                    {"initials": initials(p), "name": p.name, "me": p.pk == me_id}
                    for p in people[:3]
                ],
                extra=max(0, len(people) - 3),
            )
        )
    return out


def _diploma_link(person, path):
    from apps.diplomas import services as diplomas

    return diplomas.route_link(person, path)


TABS = (
    ("aprender", "Aprender"),
    ("practicar", "Practicar"),
    ("evaluar", "Evaluar"),
    ("recursos", "Recursos"),
    ("notas", "Notas"),
)
STEP_KEYS = (
    "portada",
    "guia",
    "practica",
    "quiz",
    "recursos",
    "notas",
)  # además de 1..N (diapositivas)


def step_url(path, level_code, key):
    return f"{reverse('paths:detail', args=[path.slug])}?nivel={level_code}&paso={key}#panel"


def level_steps(path, chapter):
    """Pasos del nivel, en orden: portada · diapositivas 1..N · guía · misiones · preguntas · recursos · notas.

    Solo presentación: no cambia códigos de nivel ni claves de misiones/preguntas (de ellas dependen XP, insignias
    y diploma). Un nivel sin diapositivas igual tiene portada, guía, práctica, quiz, recursos y notas.
    """
    code = chapter["level"].code
    slides = guides.slides_for(path.slug, code)
    steps = [{"key": "portada", "label": "Portada", "tab": "aprender"}]
    steps += [
        {"key": str(i), "label": s["title"], "tab": "aprender", "slide": s}
        for i, s in enumerate(slides, start=1)
    ]
    if guides.guide_for(path.slug, code):
        steps.append({"key": "guia", "label": "Guía rápida", "tab": "aprender"})
    if chapter["milestones"]:
        steps.append({"key": "practica", "label": "Misiones", "tab": "practicar"})
    if chapter["quiz"]:
        steps.append({"key": "quiz", "label": "Preguntas", "tab": "evaluar"})
    if chapter["resources"]:
        steps.append({"key": "recursos", "label": "Recursos", "tab": "recursos"})
    steps.append({"key": "notas", "label": "Notas del equipo", "tab": "notas"})
    for n, s in enumerate(steps, start=1):
        s["n"] = n
        s["url"] = step_url(path, code, s["key"])
    return steps


def step_context(path, chapter, step_key, prev_code, next_code):
    """Paso actual, navegación Anterior/Siguiente (al terminar salta a la portada del nivel siguiente) y pestañas."""
    steps = level_steps(path, chapter)
    index = next((i for i, s in enumerate(steps) if s["key"] == step_key), 0)  # inválido → portada
    for i, s in enumerate(steps):
        s["current"] = i == index
    step = steps[index]
    prev_url = steps[index - 1]["url"] if index > 0 else None
    if index == 0 and prev_code:
        prev_url = step_url(path, prev_code, "portada")
    next_url = steps[index + 1]["url"] if index + 1 < len(steps) else None
    next_is_level = False
    next_label = ""
    if next_url is not None:
        nxt = steps[index + 1]
        next_label = "Quiz" if nxt["key"] == "quiz" else nxt["label"]
    if next_url is None and next_code:
        next_url, next_is_level = step_url(path, next_code, "portada"), True
        next_label = "Siguiente nivel"
    tabs = []
    for tab_key, label in TABS:
        first = next((s for s in steps if s["tab"] == tab_key), None)
        if first:
            tabs.append(
                {
                    "key": tab_key,
                    "label": label,
                    "url": first["url"],
                    "active": step["tab"] == tab_key,
                }
            )
    return {
        "steps": steps,
        "step": step,
        "step_no": step["n"],
        "step_total": len(steps),
        "step_prev": prev_url,
        "step_next": next_url,
        "step_next_is_level": next_is_level,
        "step_next_label": next_label,
        "tabs": tabs,
    }


def world_context(person, path, level_code=None, step=None):
    """Todo lo que necesita la ruta interactiva de un mundo (docs/MUNDOS.md). `step`: valor de `?paso=`."""
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
        ch["quiz_right"] = sum(q["correct"] for q in quiz)
        ch["quiz_answered"] = sum(q["answered"] for q in quiz)
        ch["quiz_missing"] = len(quiz) - ch["quiz_answered"]
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
    steps = (
        step_context(
            path,
            current,
            step,
            codes[index - 1] if index > 0 else None,
            codes[index + 1] if index + 1 < len(codes) else None,
        )
        if current
        else {}
    )
    fig = figures.for_path(path)
    total_pct = percent(total_done, total_items)
    return {
        **steps,
        "path": path,
        "fig": fig,
        "fg": figure_layout.layout(
            fig["layout"],
            _stations(chapters, marks, person.pk),
            current_code=level_code,
            labels=fig["labels"],
            pct=total_pct,
        ),
        "program_code": program[0] if len(program) > 1 else "",
        "program_title": program[-1] or path.title,
        "intro": intro,
        "flow": flow,
        "chapters": chapters,
        "current": current,
        "prev_code": codes[index - 1] if index > 0 else None,
        "next_code": codes[index + 1] if index + 1 < len(codes) else None,
        "building": _floors(chapters, marks, person.pk, figures.step_label(fig["key"])),
        "flight": _waypoints(chapters, marks, person.pk),
        "stats": {
            "levels_done": sum(ch["complete"] for ch in chapters),
            "levels_total": len(chapters),
            "participants": participants,
            "pct": total_pct,
            "milestones": total_milestones,
            "questions": total_questions,
        },
        "goals": allowed_goals(path),
        "goal": goal.certification_goal if goal else "",
        "products": path.products.all(),
        "disciplines": path.disciplines.all(),
        "diploma_url": _diploma_link(person, path),
    }
