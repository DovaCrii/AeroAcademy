"""Avisos dentro de la app. `notify()` es el único punto de entrada: el canal `in_app` guarda la fila y
deja un gancho para el correo (Bloque 8)."""

import logging
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Person, PersonStatus

from .models import Announcement, Notification

log = logging.getLogger(__name__)
LIST_LIMIT = 50
BELL_LIMIT = 6


def notify(person, kind, title, body="", url="", key=""):
    """Crea un aviso. Con `key`, el mismo aviso no se repite para la misma persona. Devuelve el aviso o None."""
    if person is None or not person.is_active:
        return None
    fields = {"kind": kind, "title": title[:200], "body": body[:300], "url": url[:300]}
    if not key:
        return _email_hook(Notification.objects.create(recipient=person, **fields))
    try:
        with transaction.atomic():
            obj, created = Notification.objects.get_or_create(
                recipient=person, key=key[:120], defaults=fields
            )
    except IntegrityError:  # carrera entre dos procesos: ya existe
        return None
    return _email_hook(obj) if created else None


def _email_hook(notification):
    """Gancho del canal `email` (fuera del MVP): por ahora solo deja constancia en el log, sin el contenido."""
    log.info(
        "notify[email-hook] kind=%s recipient=%s", notification.kind, notification.recipient_id
    )
    return notification


def leads():
    return (
        Person.objects.filter(status=PersonStatus.APPROVED, is_active=True)
        .filter(groups__name__in=("lead", "admin"))
        .distinct()
    )


def notify_leads(kind, title, body="", url="", key="", exclude=None):
    for lead in leads():
        if exclude is not None and lead.pk == exclude.pk:
            continue
        notify(lead, kind, title, body, url, key)


def unread_count(person) -> int:
    return Notification.objects.filter(recipient=person, read_at__isnull=True).count()


def recent(person, limit=LIST_LIMIT):
    return list(Notification.objects.filter(recipient=person)[:limit])


def mark_read(person, pk=None) -> int:
    qs = Notification.objects.filter(recipient=person, read_at__isnull=True)
    if pk is not None:
        qs = qs.filter(pk=pk)
    return qs.update(read_at=timezone.now())


# --- anuncios -------------------------------------------------------------------------------------------------------


def publish_announcement(author, title, body, expires_on):
    if not author.is_lead:
        raise PermissionError("Solo un responsable publica anuncios.")
    title, body = (title or "").strip(), (body or "").strip()
    if not title or not body:
        raise ValueError("El anuncio necesita título y texto.")
    if len(title) > 120 or len(body) > 500:
        raise ValueError("El título admite 120 caracteres y el texto 500.")
    if not isinstance(expires_on, date) or expires_on < timezone.localdate():
        raise ValueError("La fecha de vencimiento debe ser hoy o posterior.")
    with transaction.atomic():
        ann = Announcement.objects.create(
            author=author, title=title, body=body, expires_on=expires_on
        )
        people = Person.objects.filter(status=PersonStatus.APPROVED, is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=p,
                    kind="announcement",
                    title=title,
                    body=body[:300],
                    url="/",
                    key=f"announce:{ann.pk}",
                )
                for p in people
            ]
        )
    return ann


def active_announcements(today=None):
    today = today or timezone.localdate()
    return Announcement.objects.filter(expires_on__gte=today)


def delete_announcement(ann, by):
    if not by.is_lead:
        raise PermissionError("Solo un responsable retira anuncios.")
    ann.delete()
