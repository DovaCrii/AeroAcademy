"""Foro: hilos, mensajes y consultas con respuesta aceptada (Bloque 10)."""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.gamification import game
from apps.notifications import services as notifications

from . import moderation
from .models import BODY_MAX, THREAD_TITLE_MAX, Post, Thread

ACCEPT_XP_KIND = "accepted_answer"


def can_manage(person, thread) -> bool:
    """Quien abrió el hilo y los responsables cierran, reabren y aceptan respuestas."""
    return person.pk == thread.author_id or person.is_lead


def _clean(text, limit, what):
    text = (text or "").strip()
    if not text:
        raise ValueError(f"Escribe {what}.")
    if len(text) > limit:
        raise ValueError(f"{what.capitalize()} admite hasta {limit} caracteres.")
    return text


@transaction.atomic
def create_thread(author, category, kind, title, body, disciplines=()):
    title = _clean(title, THREAD_TITLE_MAX, "un título")
    body = _clean(body, BODY_MAX, "el detalle")
    if kind not in Thread.Kind.values:
        raise ValueError("Tipo de hilo desconocido.")
    if category.retired:
        raise ValueError("Esa categoría ya no está disponible.")
    thread = Thread.objects.create(
        author=author, category=category, kind=kind, title=title, body=body
    )
    if disciplines:
        thread.disciplines.set(disciplines)
    return thread


@transaction.atomic
def reply(thread, author, body):
    if thread.is_closed:
        raise ValueError("El hilo está cerrado.")
    body = _clean(body, BODY_MAX, "el mensaje")
    post = Post.objects.create(thread=thread, author=author, body=body)
    Thread.objects.filter(pk=thread.pk).update(last_activity_at=timezone.now())
    if thread.author_id != author.pk:
        notifications.notify(
            thread.author,
            "thread_reply",
            f"{author.name} respondió tu hilo",
            thread.title,
            url=f"/foro/{thread.pk}/#post-{post.pk}",
            key=f"reply:{post.pk}",
        )
    return post


def _source(thread):
    return f"accepted:{thread.pk}"


def _revoke_accepted(thread):
    if thread.accepted_post_id:
        game.revoke(thread.accepted_post.author, _source(thread))
        game.evaluate(thread.accepted_post.author)


@transaction.atomic
def accept(thread, post, by):
    """Marca la respuesta aceptada. Da XP a quien respondió (no si se respondió a sí mismo)."""
    if not can_manage(by, thread):
        raise PermissionError("Solo quien abrió la consulta o un responsable acepta respuestas.")
    if thread.kind != Thread.Kind.QUESTION:
        raise ValueError("Solo las consultas tienen respuesta aceptada.")
    if post.thread_id != thread.pk or post.is_deleted:
        raise ValueError("Esa respuesta no es válida.")
    if thread.accepted_post_id == post.pk:
        return thread
    _revoke_accepted(thread)
    thread.accepted_post = post
    thread.save(update_fields=["accepted_post", "updated_at"])
    if post.author_id != thread.author_id:
        game.award(post.author, _source(thread), ACCEPT_XP_KIND, label=thread.title)
        game.evaluate(post.author)
        notifications.notify(
            post.author,
            "answer_accepted",
            "Tu respuesta fue aceptada",
            thread.title,
            url=f"/foro/{thread.pk}/#post-{post.pk}",
            key=f"accepted:{thread.pk}:{post.pk}",
        )
    if by.is_lead and by.pk != thread.author_id:
        moderation.log(by, "accept", thread, thread.title)
    return thread


@transaction.atomic
def unaccept(thread, by):
    if not can_manage(by, thread):
        raise PermissionError("Solo quien abrió la consulta o un responsable puede quitarla.")
    _revoke_accepted(thread)
    thread.accepted_post = None
    thread.save(update_fields=["accepted_post", "updated_at"])


@transaction.atomic
def delete_post(post, by):
    if post.author_id != by.pk or post.is_deleted:
        raise PermissionError("Solo quien escribió el mensaje puede borrarlo.")
    thread = post.thread
    if thread.accepted_post_id == post.pk:
        _revoke_accepted(thread)
        thread.accepted_post = None
        thread.save(update_fields=["accepted_post", "updated_at"])
    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])


@transaction.atomic
def set_closed(thread, by, closed: bool):
    if not can_manage(by, thread):
        raise PermissionError("Solo quien abrió el hilo o un responsable lo cierra.")
    thread.is_closed = closed
    thread.save(update_fields=["is_closed", "updated_at"])
    if by.is_lead and by.pk != thread.author_id:
        moderation.log(by, "close" if closed else "reopen", thread, thread.title)


def listing(*, category=None, kind="", discipline=None, state="", q="", show_hidden=False):
    qs = (
        Thread.objects.select_related("author", "category", "accepted_post")
        .annotate(n_posts=Count("posts", filter=Q(posts__is_deleted=False)))
        .order_by("-is_pinned", "-last_activity_at", "-id")
    )
    if not show_hidden:
        qs = qs.filter(is_hidden=False)
    if category is not None:
        qs = qs.filter(category=category)
    if kind in Thread.Kind.values:
        qs = qs.filter(kind=kind)
    if discipline is not None:
        qs = qs.filter(disciplines=discipline)
    if state == "open":  # consultas sin respuesta aceptada
        qs = qs.filter(kind=Thread.Kind.QUESTION, accepted_post__isnull=True, is_closed=False)
    elif state == "answered":
        qs = qs.filter(accepted_post__isnull=False)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q)).distinct()
    return qs


def open_questions_count() -> int:
    return Thread.objects.filter(
        kind=Thread.Kind.QUESTION, accepted_post__isnull=True, is_closed=False, is_hidden=False
    ).count()
