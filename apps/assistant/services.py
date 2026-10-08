"""Teo: límites, llamada al proveedor y respuestas de respaldo (docs/BOT.md)."""

from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import client, context
from .models import BotLog, BotUsage

MESSAGES = {
    "disabled": "Estoy durmiendo por ahora. Mientras tanto, mira la ayuda o pregunta en el foro.",
    "limit": "Por hoy medí suficiente, ¡mañana seguimos!",
    "error": "Se me empañó el lente, intenta de nuevo en un rato.",
}


@dataclass
class Answer:
    status: str  # ok | disabled | limit | error | empty
    text: str = ""
    sources: list = field(default_factory=list)
    mood: str = "idle"  # idle | happy | thinking | sleep


def enabled() -> bool:
    return client.is_configured()


def _take_slot(person) -> bool:
    """Cuenta una pregunta del día de forma atómica; False si ya alcanzó el límite."""
    today = timezone.localdate()
    with transaction.atomic():
        usage, _ = BotUsage.objects.get_or_create(person=person, day=today)
        taken = BotUsage.objects.filter(pk=usage.pk, count__lt=settings.BOT_DAILY_LIMIT).update(
            count=F("count") + 1
        )
    return bool(taken)


def _refund(person):
    BotUsage.objects.filter(person=person, day=timezone.localdate(), count__gt=0).update(
        count=F("count") - 1
    )


def remaining(person) -> int:
    used = (
        BotUsage.objects.filter(person=person, day=timezone.localdate())
        .values_list("count", flat=True)
        .first()
        or 0
    )
    return max(0, settings.BOT_DAILY_LIMIT - used)


def answer(person, question, *, extra=None, kind="ask") -> Answer:
    if not enabled():
        return Answer("disabled", MESSAGES["disabled"], mood="sleep")
    try:
        question = context.clean_question(question)
    except ValueError as exc:
        return Answer("empty", str(exc))
    if not _take_slot(person):
        return Answer("limit", MESSAGES["limit"], mood="sleep")
    messages, sources = context.build(person, question, extra=extra)
    try:
        text, tokens, latency = client.chat(messages)
    except client.BotError as exc:
        _refund(person)
        BotLog.objects.create(person=person, kind=kind, error=exc.code)
        return Answer("error", MESSAGES["error"], mood="thinking")
    BotLog.objects.create(person=person, kind=kind, tokens=tokens, latency_ms=latency)
    return Answer("ok", text, sources, mood="happy")


def forum_prefill(question):
    """Datos para abrir una consulta en el foro con la pregunta ya escrita (solo texto de la propia persona)."""
    q = " ".join((question or "").split())[:500]
    return {"titulo": q[:150], "detalle": q}
