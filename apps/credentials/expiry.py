"""Vencimientos: avisos a la persona y a los responsables, y recálculo de lo que depende de la vigencia."""

from datetime import timedelta

from django.utils import timezone

from apps.gamification import game
from apps.notifications import services as notifications

from .models import WARNING_DAYS, Credential


def expiring(today=None, days=WARNING_DAYS):
    """Verificadas que vencen dentro de `days` días (incluye hoy)."""
    today = today or timezone.localdate()
    return Credential.objects.filter(
        status=Credential.Status.VERIFIED,
        expires_on__gte=today,
        expires_on__lte=today + timedelta(days=days),
    ).select_related("owner")


def expired(today=None):
    today = today or timezone.localdate()
    return Credential.objects.filter(
        status=Credential.Status.VERIFIED, expires_on__lt=today
    ).select_related("owner")


def notify_all(today=None):
    """Tarea diaria. Idempotente: cada aviso lleva una clave por credencial y fecha de vencimiento.
    Devuelve (por vencer, vencidas, personas recalculadas)."""
    today = today or timezone.localdate()
    soon = list(expiring(today))
    gone = list(expired(today))
    for cred in soon:
        days = (cred.expires_on - today).days
        title = f"«{cred.display_title}» vence en {days} día{'s' if days != 1 else ''}"
        key = f"expiring:{cred.pk}:{cred.expires_on.isoformat()}"
        url = f"/certificados/{cred.pk}/"
        notifications.notify(cred.owner, "credential_expiring", title, url=url, key=key)
        notifications.notify_leads(
            "credential_expiring",
            f"{cred.owner.name}: {title}",
            url=url,
            key=key,
            exclude=cred.owner,
        )
    for cred in gone:
        title = f"«{cred.display_title}» está vencida"
        key = f"expired:{cred.pk}:{cred.expires_on.isoformat()}"
        url = f"/certificados/{cred.pk}/"
        notifications.notify(cred.owner, "credential_expired", title, url=url, key=key)
        notifications.notify_leads(
            "credential_expired",
            f"{cred.owner.name}: {title}",
            url=url,
            key=key,
            exclude=cred.owner,
        )
    # Lo que depende de la vigencia (p. ej. las Alas DGAC) se recalcula al vencer.
    people = {c.owner for c in gone}
    for person in people:
        game.evaluate(person, today)
    return len(soon), len(gone), len(people)
