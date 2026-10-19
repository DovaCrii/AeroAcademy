"""Contexto de las rutas externas (ej.: Bentley Learn) para el mundo Civil.

El avance sale de las credenciales verificadas: cada curso verificado es una estaca clavada; cada reliquia
(acreditación) levanta un pilar del puente. Todo se calcula; no se guarda.
"""

import math

from apps.accounts.models import PersonStatus
from apps.catalog import figure_layout, figures
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

    fig = figures.for_path(path)
    total_pct = percent(required_done, required_total)
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
        "fig": fig,
        "fg": figure_layout.layout(
            fig["layout"],
            _stations(chapters),
            current_code=level_code,
            labels=fig["labels"],
            pct=total_pct,
        ),
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
            "pct": total_pct,
            "participants": participants,
        },
        "products": path.products.all(),
        "disciplines": path.disciplines.all(),
    }


_STATE_PCT = {Credential.Status.VERIFIED: 100, Credential.Status.PENDING: 50}
_STATE_SAY = {
    Credential.Status.VERIFIED: "verificado",
    Credential.Status.PENDING: "en revisión",
    Credential.Status.REJECTED: "rechazado",
}


def _stations(chapters):
    """Estaciones de las figuras: un curso cada una (varias rutas externas tienen un solo capítulo), con su estado.

    Verificado = 100 %, en revisión = 50 %. Cada estación enlaza al capítulo del curso.
    """
    out = []
    for ch in chapters:
        for course in ch["courses"]:
            state = course["state"]
            out.append(
                figure_layout.station(
                    ch["level"].code,
                    course["obj"].resource.title,
                    _STATE_PCT.get(state, 0),
                    state == Credential.Status.VERIFIED,
                    fid=course["obj"].key,
                    say=_STATE_SAY.get(state, "por hacer"),
                    noun="Curso",
                    alias=stake_label(course["obj"].resource.title, 40),
                )
            )
    names = [s["alias"] for s in out]
    for s in out:
        if (
            names.count(s["alias"]) > 1
        ):  # dos cursos con el mismo comienzo: más palabras para distinguirlos
            s["alias"] = stake_label(s["short"], 40, 4)
    return out


_FILLER = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "and",
    "for",
    "with",
    "in",
    "on",
    "intro",
    "introduction",
    "bentley",
    "accredited",
}
STAKE_CHAR_W = 6.2  # una letra del rótulo de la estaca (10 px) ≈ 6 px
MARKER_RISE = (
    44  # «TÚ» queda 44 px sobre el eje: por encima de la estaca y de su rótulo (que ocupa -24…-14)
)


def _useful_words(title):
    words = [
        w for w in str(title).split() if w.strip("-–—·:.") and not w.isdigit()
    ]  # sin «14 -» de numeración
    return [w for w in words if w.lower().strip(".,:;") not in _FILLER] or words


def _clip(text, limit):
    text = text.rstrip(",;:")
    return text if len(text) <= limit else text[: max(limit - 1, 1)].rstrip() + "…"


def stake_label(title, limit, count=2):
    """Rótulo corto de una estaca: las `count` primeras palabras con contenido del título del curso (nunca la *key*)."""
    return _clip(" ".join(_useful_words(title)[:count]), limit)


def distinct_stake_labels(titles, limit):
    """Rótulos de estaca; cuando varios cursos comparten el comienzo (p. ej. «MicroStation …»), se quitan las palabras
    iniciales comunes del grupo para que cada rótulo muestre lo que distingue al curso."""
    first = [stake_label(t, limit) for t in titles]
    out = list(first)
    for label in dict.fromkeys(first):
        idx = [i for i, v in enumerate(first) if v == label]
        if len(idx) < 2:
            continue
        lists = [_useful_words(titles[i]) for i in idx]
        while all(len(w) > 1 for w in lists) and len({w[0].lower() for w in lists}) == 1:
            lists = [w[1:] for w in lists]
        for i, words in zip(idx, lists, strict=True):
            out[i] = _clip(" ".join(words[:2]), limit)
        shortest = min(len(w) for w in lists)
        if len({out[i] for i in idx}) < len(idx):  # uno es prefijo del otro: la cola lo distingue
            for i, words in zip(idx, lists, strict=True):
                if len(words) > shortest:
                    out[i] = _clip(" ".join(words[shortest:][:2]), limit)
    return out


def _journey(all_courses, relics):
    """Planta-perfil: una estaca por curso sobre el eje y un pilar del puente por reliquia."""
    n = len(all_courses)
    step = (WIDTH - 140) / max(n - 1, 1)
    chars = max(
        4, int(min(step, 160) * 0.9 / STAKE_CHAR_W)
    )  # el rótulo cabe en el hueco entre estacas
    stakes, last_verified_x = [], 40
    labels = distinct_stake_labels([c["obj"].resource.title for c in all_courses], chars)
    for i, item in enumerate(all_courses):
        x = 70 + i * step if n > 1 else 500
        stakes.append(
            {
                "x": _n(x),
                "y": _n(axis_y(x)),
                "key": item["obj"].key,
                "label": labels[i],
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
        "marker_y": _n(axis_y(last_verified_x) - MARKER_RISE),
        "marker_ty": _n(axis_y(last_verified_x) - MARKER_RISE + 3),
        "marker_y1": _n(axis_y(last_verified_x) - MARKER_RISE + 11),
        "marker_y2": _n(axis_y(last_verified_x) - 26),
    }
