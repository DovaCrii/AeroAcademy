"""Hoja de personaje: atributos, vitrina de insignias, árbol de habilidades y línea de tiempo.

Todo lo que sale de credenciales se filtra con la misma regla que el repositorio: un miembro solo ve de otra
persona lo verificado y visible para el equipo; la propia persona y los responsables ven todo.
"""

import math
from collections import defaultdict

from apps.credentials import services as credential_services
from apps.credentials.models import Credential

from . import game
from .avatar.careers import CAREERS
from .models import Badge, PersonBadge, XPEvent

ATTRIBUTES = [
    ("MOD", "Modelado"),
    ("CAP", "Captura"),
    ("ANA", "Análisis"),
    ("DOC", "Documentación"),
    ("NOR", "Normativa"),
    ("COL", "Colaboración"),
]
MAX_ATTRIBUTE = 20
KIND_TEXT = {
    "milestone": "Misión completada",
    "quiz": "Pregunta respondida bien",
    "chapter": "Capítulo completo",
    "path": "Campaña completa",
    "credential": "Credencial verificada",
    "free_course_promoted": "Su curso se sumó a una ruta",
    "accepted_answer": "Respuesta aceptada en Consultas",
    "note": "Nota para el equipo",
    "streak": "Racha semanal",
    "profile_completed": "Hoja de personaje completa",
}


def visible_credentials(person, viewer):
    """Credenciales verificadas de `person` que `viewer` puede ver, con sus habilidades ya cargadas."""
    rows = (
        Credential.objects.filter(owner=person, status=Credential.Status.VERIFIED)
        .filter(credential_services.visible_filter(viewer))
        .select_related("platform__vendor", "resource__platform__vendor")
        .prefetch_related("skills", "resource__skills")
        .order_by("-issued_on", "-id")
    )
    return list(rows)


def _skills_of(cred):
    found = {s.pk: s for s in cred.skills.all()}
    if cred.resource_id:
        found.update({s.pk: s for s in cred.resource.skills.all()})
    return list(found.values())


def attributes(person, viewer, creds=None):
    """Seis atributos de 0 a 20: 2 por credencial verificada con una habilidad de ese atributo (+1 cada 3 respuestas aceptadas en COL), más el bono de la carrera."""
    creds = visible_credentials(person, viewer) if creds is None else creds
    counts = dict.fromkeys((code for code, _ in ATTRIBUTES), 0)
    for cred in creds:
        for code in {s.attribute for s in _skills_of(cred) if s.attribute}:
            if code in counts:
                counts[code] += 1
    answers = XPEvent.objects.filter(person=person, kind="accepted_answer").count()
    values = {code: min(MAX_ATTRIBUTE, 2 * n) for code, n in counts.items()}
    values["COL"] = min(MAX_ATTRIBUTE, values["COL"] + answers // 3)
    bonus = career_bonus(person)
    return [
        {
            "code": code,
            "name": name,
            "value": min(MAX_ATTRIBUTE, values[code] + bonus.get(code, 0)),
            "bonus": bonus.get(code, 0),
        }
        for code, name in ATTRIBUTES
    ]


def career_bonus(person) -> dict:
    """Bono de la carrera elegida a cada atributo (por ejemplo, Geomensor: CAP +2, ANA +1)."""
    return CAREERS.get(person.character_class, {}).get("bonus", {})


def _fmt(x):
    return f"{x:.1f}"  # con punto decimal, sin depender del idioma


def hexagon(attrs, radius=84, center=100):
    """Geometría del hexágono (texto SVG ya formateado): anillos, ejes, polígono de valores y etiquetas."""
    n = len(attrs)

    def point(i, fraction):
        angle = math.radians(-90 + 360 * i / n)
        return center + radius * fraction * math.cos(angle), center + radius * fraction * math.sin(
            angle
        )

    def poly(fractions):
        return " ".join(
            f"{_fmt(x)},{_fmt(y)}" for x, y in (point(i, f) for i, f in enumerate(fractions))
        )

    rings = [poly([f] * n) for f in (0.25, 0.5, 0.75, 1.0)]
    axes = [{"x": _fmt(point(i, 1)[0]), "y": _fmt(point(i, 1)[1])} for i in range(n)]
    labels = []
    for i, a in enumerate(attrs):
        x, y = point(i, 1.2)
        labels.append({"x": _fmt(x), "y": _fmt(y), "text": a["code"], "value": a["value"]})
    values = poly([max(a["value"], 0.6) / MAX_ATTRIBUTE for a in attrs])
    return {
        "rings": rings,
        "axes": axes,
        "labels": labels,
        "values": values,
        "center": _fmt(center),
    }


def skill_tree(creds):
    """Habilidades demostradas, agrupadas por vendor, con cuántas credenciales las respaldan."""
    groups = defaultdict(lambda: defaultdict(int))
    for cred in creds:
        vendor = None
        if cred.resource_id and cred.resource.platform.vendor_id:
            vendor = cred.resource.platform.vendor.name
        elif cred.platform and cred.platform.vendor_id:
            vendor = cred.platform.vendor.name
        for skill in _skills_of(cred):
            groups[vendor or "Otras"][skill.name] += 1
    return [
        {"vendor": vendor, "skills": sorted(skills.items(), key=lambda kv: (-kv[1], kv[0]))}
        for vendor, skills in sorted(groups.items(), key=lambda kv: (kv[0] == "Otras", kv[0]))
    ]


def showcase(person):
    """Vitrina: todas las insignias; las ganadas con su fecha, las demás bloqueadas pero con la pista."""
    earned = {pb.badge_id: pb for pb in PersonBadge.objects.filter(person=person)}
    out = []
    for badge in Badge.objects.filter(retired=False):
        pb = earned.get(badge.pk)
        out.append({"badge": badge, "earned": pb is not None, "at": pb.earned_at if pb else None})
    out.sort(key=lambda row: (not row["earned"], row["badge"].order))
    return out


def timeline(person, viewer, limit=20):
    hidden_creds = set()
    if viewer.pk != person.pk and not viewer.is_lead:
        shown = {
            f"credential:{c.pk}"
            for c in Credential.objects.filter(owner=person).filter(
                credential_services.visible_filter(viewer)
            )
        }
        hidden_creds = {
            f"credential:{pk}"
            for pk in Credential.objects.filter(owner=person).values_list("pk", flat=True)
        } - shown
    rows = []
    for ev in XPEvent.objects.filter(person=person).exclude(kind="streak")[: limit * 3]:
        if ev.source in hidden_creds:
            continue
        label = KIND_TEXT.get(ev.kind, ev.kind)
        detail = ev.label if ev.kind in {"credential", "path", "free_course_promoted"} else ""
        rows.append({"when": ev.created_at, "text": label, "detail": detail, "points": ev.points})
        if len(rows) >= limit:
            break
    return rows


def completeness(person) -> bool:
    return bool(person.headline and person.bio and person.character_class and person.avatar_config)


def sync_profile(person):
    """Al completar la hoja se gana una vez la marca `profile_completed` (la insignia *Hoja Completa*)."""
    if completeness(person):
        game.award(person, "profile_completed", "profile_completed", 0)
        game.evaluate(person)


def build(person, viewer):
    creds = visible_credentials(person, viewer)
    attrs = attributes(person, viewer, creds)
    info = game.level_info(person)
    cases = showcase(person)
    return {
        "person": person,
        "is_owner": person.pk == viewer.pk,
        "info": info,
        "title": game.displayed_title(person, info["level"]),
        "attributes": attrs,
        "hex": hexagon(attrs),
        "showcase": cases,
        "earned_count": sum(1 for row in cases if row["earned"]),
        "tree": skill_tree(creds),
        "credentials": creds,
        "timeline": timeline(person, viewer),
    }
