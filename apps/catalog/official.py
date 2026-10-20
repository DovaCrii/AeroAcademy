"""Plataformas oficiales (D43): Bentley y Autodesk, con Bentley primero, y el avance de QUIEN MIRA.

El criterio de «hecho» es el mismo que usan las rutas externas y las credenciales (`progress/external.py`):
credencial **verificada** = hecho, **pendiente** = en revisión, rechazada o sin credencial = por hacer. Todo se calcula
al pintar; no se guarda nada. Solo cuenta lo de la persona que mira: nunca el avance de otras personas.
"""

from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.paths.models import LearningPath
from apps.progress.services import percent

from . import services, software

DONE, REVIEW, TODO = "done", "review", "todo"
STATE_LABEL = {DONE: "Hecho", REVIEW: "En revisión", TODO: "Por hacer"}
_LEVEL_RANK = {"fundamental": 0, "intermedio": 1, "avanzado": 2}


def state_of(states, resource_id):
    """Estado de un curso para la persona: «hecho», «en revisión» o «por hacer» (rechazado cuenta como por hacer)."""
    found = states.get(resource_id)
    status = found[0] if found else None
    if status == Credential.Status.VERIFIED:
        return DONE
    if status == Credential.Status.PENDING:
        return REVIEW
    return TODO


def is_essential(resource):
    return services.ESSENTIAL in (resource.tags or [])


def _relevance(resource):
    """Orden de «Siguiente sugerido»: lo esencial primero, del nivel más básico al más avanzado, lo oficial y el título."""
    level = _LEVEL_RANK[software.level_for_resource(resource)[0]]
    return (not is_essential(resource), level, not resource.is_official, resource.title.lower())


def mark_cards(cards, areas, states):
    """Pone `state` y `state_label` en las tarjetas de áreas oficiales; las demás quedan sin estado."""
    for r in cards:
        if areas.get(r.pk) in software.OFFICIAL:
            r.state = state_of(states, r.pk)
            r.state_label = STATE_LABEL[r.state]


def progress(resources, areas, states, paths=(), links=None):
    """{área oficial: avance} en el orden de `software.OFFICIAL` (Bentley primero).

    Cada avance trae `total`, `done`, `review`, `pct`, `essential_total`, `essential_done`, `started` y `next`:
    el curso esencial por hacer más relevante (si ya no quedan, el siguiente por hacer; si no hay, None) con su ruta.
    Sin consultas: usa lo ya cargado (recursos, áreas, rutas publicadas y enlaces) y los estados de la persona.
    """
    by_path = {p.pk: p for p in paths}
    links = links or {}
    out = {
        key: {
            "key": key,
            "label": software.AREA_LABEL[key],
            "total": 0,
            "done": 0,
            "review": 0,
            "essential_total": 0,
            "essential_done": 0,
            "todo": [],
        }
        for key in software.OFFICIAL
    }
    for r in resources:
        p = out.get(areas.get(r.pk))
        if p is None:
            continue
        state = state_of(states, r.pk)
        essential = is_essential(r)
        p["total"] += 1
        p["essential_total"] += essential
        if state == DONE:
            p["done"] += 1
            p["essential_done"] += essential
        elif state == REVIEW:
            p["review"] += 1
        else:
            p["todo"].append(r)
    out = {
        key: p for key, p in out.items() if p["total"]
    }  # un área oficial sin recursos no se muestra
    for p in out.values():
        pending = sorted(p.pop("todo"), key=_relevance)
        p["pct"] = percent(p["done"], p["total"])
        p["started"] = bool(p["done"] or p["review"])
        p["next"] = None
        if pending:
            r = pending[0]
            ids = [i for i in links.get(r.pk, ()) if i in by_path]
            route = min((by_path[i] for i in ids), key=lambda x: x.title, default=None)
            p["next"] = {"resource": r, "path": route, "essential": is_essential(r)}
    return out


def home_summary(person):
    """Tarjetas «Tus plataformas oficiales» de la portada: [avance de Bentley, avance de Autodesk].

    Consultas fijas (rutas publicadas con sus productos, recursos con sus productos, enlaces y credenciales de la
    persona): no crecen con los datos. Usa las mismas reglas de área que el catálogo, así los números coinciden.
    """
    paths = list(
        LearningPath.objects.filter(is_published=True)
        .select_related("vendor")
        .prefetch_related("products")
        .order_by("title")
    )
    every = list(services.resource_queryset(with_skills=False, ordered=False))
    links = services.published_path_links()
    general = {r.pk for r in every if services.GENERAL_TAG in (r.tags or [])}
    areas = software.areas_of(every, paths, links, general)
    states = credential_services.states_by_resource(person)
    return list(progress(every, areas, states, paths, links).values())
