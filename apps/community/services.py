"""Notas del equipo (Bloque 4). La lógica vive aquí; las vistas solo la llaman."""

from django.db import transaction
from django.utils import timezone

from apps.gamification import game
from apps.gamification.models import XPEvent

from .models import NOTE_MAX, Note

DAILY_XP_NOTES = 5  # tope diario de notas que dan XP (antitrampa, D13)
XP_TYPES = {Note.Type.WORKS, Note.Type.TIP}
TOP_TYPES = {Note.Type.WORKS, Note.Type.FAILS, Note.Type.TIP, Note.Type.ASK}


def can_delete(person, note) -> bool:
    return note.author_id == person.pk and not note.is_deleted


def _award(note):
    """5 XP por una nota *Funciona* o *Recomendación*, hasta 5 al día; toda nota cuenta para *Primera Nube*."""
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    today = XPEvent.objects.filter(
        person=note.author, kind="note", points__gt=0, created_at__gte=start
    ).count()
    points = game.POINTS["note"] if note.type in XP_TYPES and today < DAILY_XP_NOTES else 0
    game.award(note.author, f"note:{note.pk}", "note", points, note.get_type_display())


@transaction.atomic
def create_note(author, path, text, type, *, level=None, resource=None, parent=None):
    text = (text or "").strip()
    if not text:
        raise ValueError("Escribe la nota.")
    if len(text) > NOTE_MAX:
        raise ValueError(f"La nota admite hasta {NOTE_MAX} caracteres.")
    if parent is not None:
        if parent.is_deleted or parent.parent_id or parent.path_id != path.pk:
            raise ValueError("No se puede responder a esa nota.")
        type, level, resource = Note.Type.REPLY, parent.level, parent.resource
    elif type not in TOP_TYPES:
        raise ValueError("Tipo de nota desconocido.")
    if level is not None and level.path_id != path.pk:
        raise ValueError("El capítulo no es de esta ruta.")
    note = Note.objects.create(
        author=author,
        path=path,
        level=level,
        resource=resource,
        type=type,
        text=text,
        parent=parent,
    )
    _award(note)
    game.evaluate(author)
    return note


@transaction.atomic
def delete_note(note, by):
    """Solo la autora o el autor borra (borrado lógico). Sus respuestas dejan de verse y el XP se revoca."""
    if not can_delete(by, note):
        raise PermissionError("Solo quien escribió la nota puede borrarla.")
    note.is_deleted = True
    note.save(update_fields=["is_deleted", "updated_at"])
    game.revoke(note.author, f"note:{note.pk}")
    game.evaluate(note.author)


def notes_for(path, *, level=None, type=None, resource=None):
    qs = Note.objects.filter(path=path, is_deleted=False, parent__isnull=True).select_related(
        "author", "level", "resource"
    )
    if level is not None:
        qs = qs.filter(level=level)
    if type:
        qs = qs.filter(type=type)
    if resource is not None:
        qs = qs.filter(resource=resource)
    return qs


def with_replies(notes):
    """Anexa a cada nota sus respuestas visibles (una consulta para todas)."""
    notes = list(notes)
    replies = {}
    for r in (
        Note.objects.filter(parent__in=notes, is_deleted=False)
        .select_related("author")
        .order_by("created_at", "id")
    ):
        replies.setdefault(r.parent_id, []).append(r)
    for n in notes:
        n.visible_replies = replies.get(n.pk, [])
    return notes
