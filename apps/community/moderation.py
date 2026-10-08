"""Moderación del foro y de las notas (docs/MODERACION.md). Todo pasa por aquí y deja registro."""

from django.db import transaction
from django.utils import timezone

from apps.notifications import services as notifications

from .models import ModerationLog, Note, Post, Report, Thread

REASON_MAX = 300
TARGETS = {"post": Post, "note": Note}


def _require_lead(by):
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede moderar.")


def log(actor, action, obj, summary="", reason=""):
    return ModerationLog.objects.create(
        actor=actor,
        action=action,
        object_type=type(obj).__name__.lower(),
        object_id=obj.pk,
        summary=summary[:200],
        reason=(reason or "")[:REASON_MAX],
    )


def _reason(text, required=True):
    text = (text or "").strip()
    if required and not text:
        raise ValueError("Indica el motivo.")
    if len(text) > REASON_MAX:
        raise ValueError(f"El motivo admite hasta {REASON_MAX} caracteres.")
    return text


@transaction.atomic
def pin(thread, by, pinned=True):
    _require_lead(by)
    thread.is_pinned = pinned
    thread.save(update_fields=["is_pinned", "updated_at"])
    log(by, "pin" if pinned else "unpin", thread, thread.title)


@transaction.atomic
def set_hidden(obj, by, hidden, reason=""):
    """Oculta o muestra un hilo, mensaje o nota. Ocultar exige motivo; el contenido no se borra."""
    _require_lead(by)
    reason = _reason(reason, required=hidden)
    obj.is_hidden = hidden
    fields = ["is_hidden", "updated_at"]
    if hasattr(obj, "hidden_reason"):
        obj.hidden_reason = reason if hidden else ""
        fields.append("hidden_reason")
    obj.save(update_fields=fields)
    log(by, "hide" if hidden else "unhide", obj, str(obj)[:150], reason)
    if hidden:
        _undo_effects(obj)
        notifications.notify(
            obj.author,
            "content_hidden",
            "Un responsable ocultó tu contenido",
            reason,
            key=f"hidden:{type(obj).__name__.lower()}:{obj.pk}",
        )


def _undo_effects(obj):
    """Lo oculto no deja XP, respuestas aceptadas ni artículos publicados que lo copien."""
    from apps.gamification import game
    from apps.knowledge.models import Article

    if isinstance(obj, Note):
        game.revoke(obj.author, f"note:{obj.pk}")
        game.evaluate(obj.author)
    elif isinstance(obj, Post):
        thread = Thread.objects.select_for_update().get(pk=obj.thread_id)
        if thread.accepted_post_id == obj.pk:
            from . import forum

            forum._revoke_accepted(thread)
            thread.accepted_post = None
            thread.save(update_fields=["accepted_post", "updated_at"])
    elif isinstance(obj, Thread):
        Article.objects.filter(source_thread=obj).update(is_published=False)


@transaction.atomic
def move_thread(thread, by, category, disciplines=()):
    _require_lead(by)
    if category.retired:
        raise ValueError("Esa categoría ya no está disponible.")
    old = thread.category.name
    thread.category = category
    thread.save(update_fields=["category", "updated_at"])
    thread.disciplines.set(disciplines)
    log(by, "move", thread, f"{old} → {category.name}")


@transaction.atomic
def rename_thread(thread, by, title):
    _require_lead(by)
    title = (title or "").strip()
    if not title or len(title) > 150:
        raise ValueError("El título debe tener entre 1 y 150 caracteres.")
    old, thread.title = thread.title, title
    thread.save(update_fields=["title", "updated_at"])
    log(by, "rename", thread, f"{old} → {title}")


# --- reportes -------------------------------------------------------------------------------------------------------


def target_of(report):
    model = TARGETS.get(report.target_type)
    return model.objects.filter(pk=report.target_id).first() if model else None


@transaction.atomic
def report_content(reporter, kind, pk, reason):
    model = TARGETS.get(kind)
    if model is None:
        raise ValueError("No se puede reportar eso.")
    target = model.objects.filter(
        pk=pk, is_deleted=False, is_hidden=False
    ).first()  # no revela lo oculto
    if target is None:
        raise ValueError("Ese contenido ya no existe.")
    if target.author_id == reporter.pk:
        raise ValueError("No puedes reportar tu propio contenido.")
    reason = _reason(reason)
    if Report.objects.filter(
        reporter=reporter, target_type=kind, target_id=pk, status=Report.Status.OPEN
    ).exists():
        raise ValueError("Ya reportaste esto; un responsable lo revisará.")
    rep = Report.objects.create(reporter=reporter, target_type=kind, target_id=pk, reason=reason)
    notifications.notify_leads(
        "report",
        "Nuevo reporte en el foro" if kind == "post" else "Nuevo reporte de una nota",
        reason[:120],
        url="/moderacion/",
        key=f"report:{rep.pk}",
        exclude=reporter,
    )
    return rep


@transaction.atomic
def resolve_report(report, by, *, hide, reason=""):
    """Un responsable cierra el reporte: oculta el contenido o lo descarta."""
    _require_lead(by)
    if report.status != Report.Status.OPEN:
        raise ValueError("El reporte ya estaba resuelto.")
    target = target_of(report)
    if hide:
        if target is None:
            raise ValueError("El contenido ya no existe.")
        set_hidden(target, by, True, reason or report.reason)
        report.status = Report.Status.HIDDEN
    else:
        report.status = Report.Status.DISMISSED
        log(by, "dismiss_report", report, report.reason[:150], reason)
    report.resolved_by, report.resolved_at = by, timezone.now()
    report.save(update_fields=["status", "resolved_by", "resolved_at", "updated_at"])


def open_reports():
    return Report.objects.filter(status=Report.Status.OPEN)
