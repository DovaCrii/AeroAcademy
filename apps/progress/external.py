"""Contexto de las rutas externas (ej.: Bentley Learn) para el mundo Civil.

El avance sale de las credenciales verificadas: cada curso verificado es una estaca clavada; cada reliquia
(acreditación) levanta un pilar del puente. Todo se calcula; no se guarda.
"""

import math

from apps.accounts.models import PersonStatus
from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.paths import services as path_services
from apps.paths.models import ExternalCourse, Level

from .services import percent

# Geometría del dibujo (viewBox 1000 × 400): planta arriba, perfil abajo.
WIDTH, AXIS_Y, DECK_Y = 1000, 110, 268
BRIDGE = (600, 900)


def axis_y(x):
    return AXIS_Y + 26 * math.sin((x - 40) / 920 * 2 * math.pi * 1.4)


def ground_y(x):
    """Terreno del perfil: ondulado y con un valle bajo el puente."""
    y = 296 + 9 * math.sin(x / 70) + 5 * math.cos(x / 33)
    low, high = BRIDGE
    if low <= x <= high:
        y += 78 * math.sin((x - low) / (high - low) * math.pi) ** 0.7
    return y


def _n(value):
    """Coordenada como texto con punto decimal: el idioma español de Django escribiría una coma."""
    return f"{value:.1f}"


def _best_state(states, resource_id):
    found = states.get(resource_id)
    return (found[0], found[1]) if found else ("none", None)


def external_context(person, path, level_code=None):
    chapters = path_services.path_detail(path)
    states = credential_services.states_by_resource(person)
    free = list(credential_services.free_courses_of(person, path))

    all_courses, required_total, required_done = [], 0, 0
    for index, ch in enumerate(chapters):
        level = ch["level"]
        courses = []
        for course in ch["courses"]:
            state, cred_id = _best_state(states, course.resource_id)
            courses.append({"obj": course, "state": state, "cred_id": cred_id})
        required = [c for c in courses if c["obj"].is_required]
        any_verified = any(c["state"] == Credential.Status.VERIFIED for c in courses)
        if level.completion_rule == Level.CompletionRule.ANY_ONE:
            total, done = (1, int(any_verified)) if courses else (0, 0)
        else:
            total = len(required)
            done = sum(c["state"] == Credential.Status.VERIFIED for c in required)
        ch.update(
            courses=courses,
            km=f"{index}+000",
            done=done,
            total=total,
            pct=percent(done, total),
            complete=bool(total) and done == total,
            free_credentials=free if level.is_free_courses else [],
        )
        required_total += total
        required_done += done
        all_courses.extend(courses)

    codes = [ch["level"].code for ch in chapters]
    if level_code not in codes:
        pending = next((ch for ch in chapters if ch["total"] and not ch["complete"]), None)
        level_code = (pending or chapters[0])["level"].code if chapters else None
    index = codes.index(level_code) if level_code else 0

    verified = [c for c in all_courses if c["state"] == Credential.Status.VERIFIED]
    pending_n = sum(c["state"] == Credential.Status.PENDING for c in all_courses)
    relics = [c for c in all_courses if c["obj"].reward == ExternalCourse.Reward.RELIC]
    participants = (
        Credential.objects.filter(
            path=path, status=Credential.Status.VERIFIED, owner__status=PersonStatus.APPROVED
        )
        .values("owner")
        .distinct()
        .count()
    )

    return {
        "path": path,
        "chapters": chapters,
        "current": chapters[index] if chapters else None,
        "prev_code": codes[index - 1] if index > 0 else None,
        "next_code": codes[index + 1] if index + 1 < len(codes) else None,
        "program_code": "",
        "journey": _journey(all_courses, relics),
        "stats": {
            "courses": len(all_courses),
            "verified": len(verified),
            "pending": pending_n,
            "relics": len(relics),
            "relics_verified": sum(c["state"] == Credential.Status.VERIFIED for c in relics),
            "chapters": len(chapters),
            "chapters_done": sum(ch["complete"] for ch in chapters),
            "pct": percent(required_done, required_total),
            "participants": participants,
        },
        "products": path.products.all(),
        "disciplines": path.disciplines.all(),
    }


def _journey(all_courses, relics):
    """Planta-perfil: una estaca por curso sobre el eje y un pilar del puente por reliquia."""
    n = len(all_courses)
    step = (WIDTH - 140) / max(n - 1, 1)
    stakes, last_verified_x = [], 40
    for i, item in enumerate(all_courses):
        x = 70 + i * step if n > 1 else 500
        stakes.append(
            {
                "x": _n(x),
                "y": _n(axis_y(x)),
                "key": item["obj"].key,
                "title": item["obj"].resource.title,
                "state": item["state"],
                "relic": item["obj"].reward == ExternalCourse.Reward.RELIC,
            }
        )
        if item["state"] == Credential.Status.VERIFIED:
            last_verified_x = x
    pavement = " ".join(f"{x},{axis_y(x):.1f}" for x in range(40, int(last_verified_x) + 1, 10))
    axis = " ".join(f"{x},{axis_y(x):.1f}" for x in range(40, 961, 10))
    ground = " ".join(f"{x},{ground_y(x):.1f}" for x in range(40, 961, 10))

    low, high = BRIDGE
    m = max(len(relics), 1)
    piers = []
    for j, item in enumerate(relics):
        x = low + 30 + j * ((high - low - 60) / max(m - 1, 1)) if m > 1 else (low + high) / 2
        piers.append(
            {
                "x": _n(x - 7),
                "cx": _n(x),
                "top": DECK_Y + 2,
                "height": _n(ground_y(x) - DECK_Y - 2),
                "label_y": _n(ground_y(x) + 20),
                "state": item["state"],
                "title": item["obj"].resource.title,
                "n": j + 1,
            }
        )
    return {
        "stakes": stakes,
        "pavement": pavement if last_verified_x > 40 else "",
        "axis": axis,
        "ground": ground,
        "piers": piers,
        "deck": {"x": low, "width": high - low, "y": DECK_Y},
        "marker_x": _n(last_verified_x),
        "marker_y": _n(axis_y(last_verified_x)),
        "marker_ty": _n(axis_y(last_verified_x) + 4),
    }
