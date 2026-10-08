"""Atajos de Teo: respuestas inmediatas calculadas en la VM, sin el modelo.

Funcionan aunque Teo «duerma» (sin clave o sin servicio) y no gastan el límite diario. Como no salen de la VM, pueden
usar datos de la propia persona (sus vencimientos, su avance) que nunca se envían a la API.
"""

from django.urls import reverse
from django.utils import timezone

from apps.core import dashboard
from apps.credentials import expiry
from apps.paths.models import ExternalCourse, LearningPath, LevelResource, Milestone
from apps.progress.models import MilestoneCheck

from .models import BotLog
from .services import Answer

SHORTCUTS = [
    ("mision", "¿Qué me falta?"),
    ("vence", "¿Qué vence pronto?"),
    ("curso", "Recomiéndame un curso"),
    ("subir", "¿Cómo subo un certificado?"),
]
LIMIT = 5


def _catalog_link(title):
    from urllib.parse import quote

    return reverse("catalog:resources") + "?q=" + quote(title)


def _mission(person):
    mission = dashboard.suggested_mission(person)
    if mission is None:
        return Answer(
            "ok",
            "¡Completaste todas las campañas disponibles! Cuando se abra una ruta nueva te aviso en la campana.",
            [{"n": 1, "title": "Ver las rutas", "url": reverse("paths:index")}],
            mood="happy",
        )
    path = mission["path"]
    lines = [
        f"Tu próxima misión: {mission['title']}.",
        f"{mission['detail']} · llevas {mission['pct']} % de la campaña.",
    ]
    if path.kind == LearningPath.Kind.STRUCTURED:
        done = set(
            MilestoneCheck.objects.filter(person=person, milestone__path=path).values_list(
                "milestone_id", flat=True
            )
        )
        pending = [
            dashboard._plain(m.text)
            for m in Milestone.objects.filter(path=path, retired=False).select_related("level")
            if m.pk not in done
        ]
        if len(pending) > 1:
            lines.append("Después vienen: " + "; ".join(pending[1:LIMIT]) + ".")
    return Answer(
        "ok",
        "\n".join(lines),
        [
            {"n": 1, "title": "Ir a la misión", "url": mission["url"]},
            {"n": 2, "title": path.title, "url": reverse("paths:detail", args=[path.slug])},
        ],
        mood="happy",
    )


def _expiring(person):
    today = timezone.localdate()
    soon = list(expiry.expiring(today).filter(owner=person).order_by("expires_on"))
    gone = list(expiry.expired(today).filter(owner=person).order_by("-expires_on"))
    if not soon and not gone:
        return Answer(
            "ok",
            f"Nada vence en los próximos {expiry.WARNING_DAYS} días. ¡Buena medición!",
            [{"n": 1, "title": "Mis certificados", "url": reverse("credentials:mine")}],
            mood="happy",
        )
    lines = []
    for cred in soon[:LIMIT]:
        lines.append(
            f"• «{cred.display_title}» vence el {cred.expires_on:%d/%m/%Y} (en {cred.days_to_expiry} días)."
        )
    for cred in gone[:LIMIT]:
        lines.append(f"• «{cred.display_title}» venció el {cred.expires_on:%d/%m/%Y}.")
    lines.append("Renuévalas y sube el certificado nuevo para que vuelva a revisión.")
    return Answer(
        "ok",
        "\n".join(lines),
        [{"n": 1, "title": "Vencimientos", "url": reverse("credentials:expirations")}],
        mood="thinking",
    )


def _course(person):
    mission = dashboard.suggested_mission(person)
    if mission is None:
        return Answer(
            "ok",
            "Ya completaste las campañas: explora el catálogo para seguir aprendiendo.",
            [{"n": 1, "title": "Catálogo", "url": reverse("catalog:resources")}],
        )
    path = mission["path"]
    resources = []
    if path.kind == LearningPath.Kind.STRUCTURED:
        done = set(
            MilestoneCheck.objects.filter(person=person, milestone__path=path).values_list(
                "milestone_id", flat=True
            )
        )
        nxt = next(
            (
                m
                for m in Milestone.objects.filter(path=path, retired=False).select_related("level")
                if m.pk not in done
            ),
            None,
        )
        if nxt is not None:
            resources = [
                lr.resource
                for lr in LevelResource.objects.filter(level=nxt.level)
                .select_related("resource")
                .order_by("order")[:3]
            ]
    else:
        resources = [
            c.resource
            for c in ExternalCourse.objects.filter(path=path, is_required=True, retired=False)
            .select_related("resource")
            .order_by("level__order", "order")[:3]
        ]
    if not resources:
        return Answer(
            "ok",
            f"Sigue con tu misión en {path.title}.",
            [{"n": 1, "title": "Ir a la misión", "url": mission["url"]}],
        )
    sources = [
        {"n": i, "title": r.title, "url": _catalog_link(r.title)}
        for i, r in enumerate(resources, start=1)
    ]
    return Answer(
        "ok",
        f"Para avanzar en {path.title} te recomiendo empezar por:\n"
        + "\n".join(f"[{s['n']}] {s['title']}" for s in sources),
        sources,
        mood="happy",
    )


def _upload(person):
    return Answer(
        "ok",
        "En Certificados > «Subir certificado» eliges el archivo (PDF, PNG o JPG, hasta 10 MB) y completas los datos. "
        "Si el curso es de una ruta con certificado externo (Bentley), usa «Registrar curso + certificado» dentro de la ruta. "
        "Un responsable lo revisa y, al verificarlo, se marca la misión y ganas XP.",
        [
            {"n": 1, "title": "Subir certificado", "url": reverse("credentials:create")},
            {
                "n": 2,
                "title": "Guía paso a paso",
                "url": reverse("assistant:help", args=["subir-certificado"]),
            },
        ],
    )


HANDLERS = {"mision": _mission, "vence": _expiring, "curso": _course, "subir": _upload}


def answer(person, key):
    handler = HANDLERS.get(key)
    if handler is None:
        return Answer("empty", "No conozco ese atajo.")
    result = handler(person)
    BotLog.objects.create(person=person, kind="quick")  # solo metadatos, como siempre
    return result


def label(key):
    return dict(SHORTCUTS).get(key, "")
