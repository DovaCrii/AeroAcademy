"""Mapa de metro de las rutas (docs/CURSOS.md): disciplinas = líneas, rutas = estaciones.

Todo sale de la base de datos y es determinista:

- Una **línea** por disciplina con rutas visibles (más «Otras rutas» si alguna ruta no tiene disciplina). Cada
  línea es una vía horizontal recta en su propia fila, de su primera a su última estación.
- Una **estación** por ruta visible. Si la ruta sirve a varias disciplinas es un **transbordo**: una cápsula
  vertical en una sola columna, con un punto en cada una de sus líneas. Si salta filas cuya línea no la sirve,
  ese tramo es un conector fino (no una parada).
- **Orden de filas:** se prueba cada permutación de las líneas (fuerza bruta hasta 8; escalada de pares si hay
  más) y se elige la que menos filas hace cruzar a los transbordos.
- **Columnas:** las rutas se ordenan («101» primero, luego empresa y título) y cada una toma la primera columna
  libre a la derecha de lo último de sus líneas; rutas con tramos de filas que no se solapan comparten columna.
- El avance personal se calcula con consultas agrupadas (no crecen con las rutas ni con el avance).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import permutations

from django.db.models import Count, F, Max, Q
from django.urls import reverse

from apps.catalog.models import Discipline

from .models import ExternalCourse, Level, Milestone, QuizQuestion
from .services import visible_paths

COL_W = 76  # separación horizontal entre columnas
ROW_H = 96  # separación vertical entre líneas
TOP = 66  # sitio para el marcador «Estás aquí» sobre la primera fila
PILL_H = 24
LABEL_CHARS = 14
STUB = 18  # tramo de vía entre la última estación y la píldora con el nombre
BRUTE_MAX = 8

# Colores por disciplina conocida (tokens de tokens.css, claros y oscuros); el resto cicla por --mm-N.
_KNOWN_COLOR = {
    "arquitectura": "var(--d-arq)",
    "civil-estructural": "var(--d-civ)",
    "topografia": "var(--d-top)",
    "mecanica": "var(--d-mec)",
    "captura-rpa": "var(--d-cap)",
    "transversal": "var(--d-doc)",
    "ia-datos": "var(--d-kno)",
}
_EXTRA_COLORS = ["var(--mm-1)", "var(--mm-2)", "var(--mm-3)", "var(--mm-4)"]

OTHERS_SLUG = "otras"


@dataclass
class Line:
    slug: str
    name: str
    color: str
    row: int = 0
    y: int = 0
    stations: list = field(default_factory=list)
    d: str = ""
    pill_left: dict = field(default_factory=dict)
    pill_right: dict = field(default_factory=dict)


def _pill_width(name):
    return int(len(name) * 6.1 + 20)


def _wrap(title):
    """Hasta dos renglones de ~16 caracteres, cortando por palabras."""
    words = title.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > LABEL_CHARS:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return [ln if len(ln) <= LABEL_CHARS + 1 else ln[:LABEL_CHARS] + "…" for ln in lines]


def _sort_key(path):
    """«101» primero; dentro de cada grupo, primero los transbordos (cápsulas más compactas), luego empresa y título."""
    return (
        0 if "101" in path.slug else 1,
        -len(path.disciplines.all()),
        path.vendor.order,
        path.title.lower(),
        path.slug,
    )


def _order_cost(order, groups):
    """Filas que cruzan los transbordos: tramo total + triple penalización por filas saltadas que no sirven."""
    pos = {line: i for i, line in enumerate(order)}
    cost = 0
    for group, n in groups.items():
        rows = [pos[g] for g in group]
        span = max(rows) - min(rows)
        cost += n * (span + 3 * (span + 1 - len(rows)))
    return cost


def best_row_order(slugs, groups):
    """Orden de filas con menos cruces. `slugs` llega en orden base; el empate lo gana el orden base."""
    slugs = list(slugs)
    groups = {g: n for g, n in groups.items() if len(g) > 1}
    if len(slugs) <= 2 or not groups:
        return slugs
    if len(slugs) <= BRUTE_MAX:
        return list(
            min(
                permutations(slugs),
                key=lambda o: (_order_cost(o, groups), [slugs.index(s) for s in o]),
            )
        )
    order = slugs[:]  # muchas líneas: escalada por intercambio de pares
    best = _order_cost(order, groups)
    improved = True
    while improved:
        improved = False
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                order[i], order[j] = order[j], order[i]
                c = _order_cost(order, groups)
                if c < best:
                    best, improved = c, True
                else:
                    order[i], order[j] = order[j], order[i]
    return order


def _progress(person, paths):
    """ruta.id → {"pct", "state" (todo|progress|done), "last"}; consultas agrupadas, sin N+1."""
    from apps.credentials.models import Credential
    from apps.progress.models import MilestoneCheck, QuizAnswer

    ids = [p.pk for p in paths]
    total = defaultdict(int)
    for model in (Milestone, QuizQuestion):
        rows = (
            model.objects.filter(path_id__in=ids, retired=False)
            .values("path_id")
            .annotate(n=Count("id"))
        )
        for r in rows:
            total[r["path_id"]] += r["n"]
    done, last = defaultdict(int), {}

    def touch(pid, when):
        if when and (pid not in last or when > last[pid]):
            last[pid] = when

    for r in (
        MilestoneCheck.objects.filter(
            person=person, milestone__path_id__in=ids, milestone__retired=False
        )
        .values("milestone__path_id")
        .annotate(n=Count("id"), last=Max("checked_at"))
    ):
        done[r["milestone__path_id"]] += r["n"]
        touch(r["milestone__path_id"], r["last"])
    for r in (
        QuizAnswer.objects.filter(person=person, question__path_id__in=ids)
        .values("question__path_id")
        .annotate(
            right=Count(
                "id", filter=Q(selected_index=F("question__answer_index"), question__retired=False)
            ),
            last=Max("answered_at"),
        )
    ):
        done[r["question__path_id"]] += r["right"]
        touch(r["question__path_id"], r["last"])

    # Rutas externas: cursos con certificado verificado (misma regla que progress.external).
    courses = defaultdict(lambda: defaultdict(list))
    for c in ExternalCourse.objects.filter(path_id__in=ids, retired=False).values(
        "path_id", "level_id", "resource_id", "is_required", "level__completion_rule"
    ):
        courses[c["path_id"]][(c["level_id"], c["level__completion_rule"])].append(c)
    creds = defaultdict(lambda: {"verified": False, "any": False})
    for resource_id, status, created in Credential.objects.filter(
        owner=person, resource__isnull=False
    ).values_list("resource_id", "status", "created_at"):
        creds[resource_id]["any"] = True
        creds[resource_id]["verified"] |= status == Credential.Status.VERIFIED
        creds[resource_id]["created"] = max(created, creds[resource_id].get("created", created))
    ext_touched = set()
    for pid, levels in courses.items():
        ext_total = ext_done = 0
        for (_lid, rule), items in levels.items():
            states = [creds.get(i["resource_id"]) for i in items]
            for s in states:
                if s:
                    ext_touched.add(pid)
                    touch(pid, s["created"])
            if rule == Level.CompletionRule.ANY_ONE:
                ext_total += 1
                ext_done += int(any(s and s["verified"] for s in states))
            else:
                req = [(i, s) for i, s in zip(items, states, strict=True) if i["is_required"]]
                ext_total += len(req)
                ext_done += sum(bool(s and s["verified"]) for _i, s in req)
        total[pid] += ext_total
        done[pid] += ext_done

    result = {}
    for pid in ids:
        t, d = total[pid], done[pid]
        pct = int(100 * d / t + 0.5) if t else 0
        if t and d >= t:
            state = "done"
        elif d or pid in ext_touched or pid in last:
            state = "progress"
        else:
            state = "todo"
        result[pid] = {"pct": pct, "state": state, "last": last.get(pid)}
    return result


def build_map(person):
    """Todo lo que pinta `paths/map.html`: líneas, estaciones, coordenadas y avance."""
    paths = sorted(visible_paths(person).prefetch_related("disciplines"), key=_sort_key)
    disc_order = {d.pk: i for i, d in enumerate(Discipline.objects.all())}
    disc_rows = {}  # slug → Discipline
    for p in paths:
        for d in p.disciplines.all():
            disc_rows[d.slug] = d

    base = []  # (slug, nombre, color) en el orden base de las disciplinas
    for n, d in enumerate(sorted(disc_rows.values(), key=lambda d: (disc_order[d.pk], d.slug))):
        base.append(
            (d.slug, d.name, _KNOWN_COLOR.get(d.slug, _EXTRA_COLORS[n % len(_EXTRA_COLORS)]))
        )
    if any(not p.disciplines.all() for p in paths):
        base.append((OTHERS_SLUG, "Otras rutas", "var(--mm-0)"))

    route_lines = {p.pk: [d.slug for d in p.disciplines.all()] or [OTHERS_SLUG] for p in paths}
    groups = Counter(frozenset(v) for v in route_lines.values())
    order = best_row_order([b[0] for b in base], groups)
    info = {s: (name, color) for s, name, color in base}
    lines = [Line(s, info[s][0], info[s][1], row=i) for i, s in enumerate(order)]
    by_slug = {ln.slug: ln for ln in lines}
    for ln in lines:
        ln.y = TOP + ln.row * ROW_H

    progress = _progress(person, paths) if paths else {}
    stations, occupied, last_col = [], set(), defaultdict(lambda: -1)
    for p in paths:
        mine = sorted((by_slug[s] for s in route_lines[p.pk]), key=lambda ln: ln.row)
        rows = [ln.row for ln in mine]
        span = range(rows[0], rows[-1] + 1)
        col = max(last_col[r] for r in rows) + 1
        while any((col, r) in occupied for r in span):
            col += 1
        occupied.update((col, r) for r in span)
        for r in rows:
            last_col[r] = col
        # Tramos contiguos de filas servidas = cápsulas; los saltos entre ellos, conectores finos.
        runs, cur = [], [mine[0]]
        for ln in mine[1:]:
            if ln.row == cur[-1].row + 1:
                cur.append(ln)
            else:
                runs.append(cur)
                cur = [ln]
        runs.append(cur)
        prog = progress[p.pk]
        st = {
            "slug": p.slug,
            "title": p.title,
            "url": reverse("paths:detail", args=[p.slug]),
            "col": col,
            "lines": mine,
            "capsules": [
                {
                    "y": r[0].y - 13,
                    "h": r[-1].y - r[0].y + 26,
                    "gy": r[0].y - 17,
                    "gh": r[-1].y - r[0].y + 34,
                }
                for r in runs
            ],
            "links": [{"a": a[-1].y, "b": b[0].y} for a, b in zip(runs, runs[1:], strict=False)],
            "hit_y": mine[0].y - 26,
            "hit_h": mine[-1].y - mine[0].y + (74 if len(mine) > 1 else 70),
            "label_dy": 28 if len(mine) > 1 else 24,
            "top": mine[0].y,
            "bottom": mine[-1].y,
            "primary": mine[0],
            "interchange": len(mine) > 1,
            "label": _wrap(p.title),
            "pct": prog["pct"],
            "state": prog["state"],
            "last": prog["last"],
            "current": False,
        }
        stations.append(st)
        for ln in mine:
            ln.stations.append(st)

    # Margen izquierdo justo: que la píldora de cada línea quepa a la izquierda de su primera estación.
    left = max(
        (_pill_width(ln.name) + STUB + 6 - ln.stations[0]["col"] * COL_W for ln in lines), default=0
    )
    for s in stations:
        s["x"] = left + s["col"] * COL_W
    right = 0
    for ln in lines:
        pw = _pill_width(ln.name)
        start_x = ln.stations[0]["x"] - STUB
        end_x = ln.stations[-1]["x"] + STUB
        ln.d = f"M{start_x} {ln.y} L{end_x} {ln.y}"
        right = max(right, end_x + pw)
        ln.pill_left = {
            "x": start_x - pw,
            "y": ln.y - PILL_H // 2,
            "w": pw,
            "tx": start_x - pw // 2,
        }
        ln.pill_right = {"x": end_x, "y": ln.y - PILL_H // 2, "w": pw, "tx": end_x + pw // 2}
    width = right + 16
    height = TOP + max(len(lines) - 1, 0) * ROW_H + 74

    # «Estás aquí»: ruta en curso con actividad más reciente (si no, la última tocada).
    active = [s for s in stations if s["last"]]
    pool = [s for s in active if s["state"] == "progress"] or active
    if pool:
        max(pool, key=lambda s: s["last"])["current"] = True

    interchanges = [s for s in stations if s["interchange"]]
    return {
        "lines": lines,
        "stations": stations,
        "interchanges": interchanges,
        "width": width,
        "height": height,
        "PILL_H": PILL_H,
        "counts": {
            "lines": len(lines),
            "stations": len(stations),
            "interchanges": len(interchanges),
            "done": sum(s["state"] == "done" for s in stations),
        },
    }
