"""Seguimiento de Teo: un empujón semanal, dentro de la app, a quien lleva una semana sin avanzar.

No llama a ningún servicio externo ni usa el modelo: es el mismo cálculo de la «misión sugerida» de la portada, así que
nada personal sale de la VM. Es idempotente: cada aviso lleva una clave por persona y semana.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Person, PersonStatus
from apps.core import dashboard
from apps.credentials.models import Credential
from apps.gamification.models import XPEvent
from apps.gamification.rules import LEARNING_KINDS
from apps.notifications import services as notifications

IDLE_DAYS = 7


def _week_key(today):
    iso = today.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _idle(person, now):
    """Sin ninguna acción de aprendizaje en la última semana (y con la cuenta ya más antigua que eso)."""
    cutoff = now - timedelta(days=IDLE_DAYS)
    if person.created_at > cutoff:
        return False
    return not XPEvent.objects.filter(
        person=person, kind__in=LEARNING_KINDS, created_at__gte=cutoff
    ).exists()


def run(today=None):
    """Tarea semanal. Devuelve (personas avisadas, resumen enviado a responsables)."""
    if not getattr(settings, "TEO_NUDGES", True):
        return 0, 0
    today = today or timezone.localdate()
    now = timezone.now()
    week = _week_key(today)
    nudged = idle_total = 0
    for person in Person.objects.filter(status=PersonStatus.APPROVED, is_active=True):
        if not _idle(person, now):
            continue
        idle_total += 1
        mission = dashboard.suggested_mission(person)
        if mission is None:
            continue
        sent = notifications.notify(
            person,
            "teo_nudge",
            "Teo: ¿retomamos? Esta es tu próxima misión",
            f"{mission['title']} · {mission['detail']}"[:300],
            url=mission["url"],
            key=f"teo-week:{week}",
        )
        nudged += int(sent is not None)
    summary = 0
    if idle_total or Credential.objects.filter(status=Credential.Status.PENDING).exists():
        pending = Credential.objects.filter(status=Credential.Status.PENDING).count()
        stale = Credential.objects.filter(
            status=Credential.Status.PENDING, created_at__lte=now - timedelta(days=IDLE_DAYS)
        ).count()
        for lead in notifications.leads():
            sent = notifications.notify(
                lead,
                "teo_digest",
                "Teo: resumen de la semana",
                f"{idle_total} persona(s) sin avance en {IDLE_DAYS} días · {pending} certificado(s) por revisar"
                + (f" ({stale} esperan hace más de {IDLE_DAYS} días)" if stale else ""),
                url="/equipo/",
                key=f"teo-digest:{week}",
            )
            summary += int(sent is not None)
    return nudged, summary
