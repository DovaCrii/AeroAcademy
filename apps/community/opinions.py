"""Opinar en el foro: reacciones a hilos y mensajes, y encuestas rápidas en «Ideas y mejoras»."""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.gamification import game
from apps.gamification.models import XPEvent

from . import moderation
from .models import PollOption, PollVote, Post, Reaction, Thread

KINDS = list(Reaction.Kind.values)
XP_KIND = "reaction"
XP_REACTION_KIND = Reaction.Kind.USEFUL  # solo «Útil» da XP a quien escribió (1 punto)
XP_POINTS = 1
DAILY_REACTION_XP = 10  # puntos por reacciones que una persona puede ganar al día (antitrampa, D13)

POLL_CATEGORY = "ideas-mejoras"
POLL_MIN, POLL_MAX, OPTION_MAX = 2, 6, 80


# --- visibilidad ----------------------------------------------------------------------------------------------------


def _thread_of(obj):
    return obj if isinstance(obj, Thread) else obj.thread


def is_open_to_opinion(obj) -> bool:
    """Lo oculto o borrado no recibe reacciones."""
    if isinstance(obj, Post) and (obj.is_hidden or obj.is_deleted):
        return False
    return not _thread_of(obj).is_hidden


def _reactions_of(obj):
    return (
        Reaction.objects.filter(thread=obj)
        if isinstance(obj, Thread)
        else Reaction.objects.filter(post=obj)
    )


# --- XP de «Útil» ---------------------------------------------------------------------------------------------------


def _source(reaction) -> str:
    target = f"t{reaction.thread_id}" if reaction.thread_id else f"p{reaction.post_id}"
    return f"reaction:{target}:{reaction.person_id}"


def _earned_today(author) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(
        XPEvent.objects.filter(
            person=author, kind=XP_KIND, points__gt=0, created_at__gte=start
        ).values_list("points", flat=True)
    )


def resync_xp(obj):
    """Reconcilia el XP de las reacciones «Útil» de un hilo o mensaje con su estado (visible u oculto).

    Idempotente: ocultar o borrar lo revoca; mostrarlo de nuevo lo devuelve, respetando el tope diario.
    """
    visible = is_open_to_opinion(obj)
    author = obj.author
    changed = False
    for r in _reactions_of(obj).filter(kind=XP_REACTION_KIND):
        if r.person_id == author.pk:
            continue
        source = _source(r)
        if not visible:
            changed |= game.revoke(author, source)
        elif not XPEvent.objects.filter(person=author, source=source).exists():
            points = XP_POINTS if _earned_today(author) < DAILY_REACTION_XP else 0
            changed |= game.award(author, source, XP_KIND, points, "Reacción «Útil»")
    if changed:
        game.evaluate(author)


# --- reacciones -----------------------------------------------------------------------------------------------------


@transaction.atomic
def toggle_reaction(person, obj, kind) -> bool:
    """Pone o quita la reacción de `person`. Devuelve si quedó puesta."""
    if kind not in KINDS:
        raise ValueError("Esa reacción no existe.")
    if not is_open_to_opinion(obj):
        raise ValueError("Ese contenido ya no está disponible.")
    if obj.author_id == person.pk:
        raise ValueError("No puedes reaccionar a tu propio contenido.")
    target = {"thread": obj} if isinstance(obj, Thread) else {"post": obj}
    existing = Reaction.objects.filter(person=person, kind=kind, **target).first()
    if existing:
        if kind == XP_REACTION_KIND:
            game.revoke(obj.author, _source(existing))
            game.evaluate(obj.author)
        existing.delete()
        return False
    Reaction.objects.create(person=person, kind=kind, **target)
    if kind == XP_REACTION_KIND:
        resync_xp(obj)
    return True


def _bar(counts, mine, can_react):
    return {
        "can_react": can_react,
        "items": [
            {
                "kind": k,
                "emoji": Reaction.EMOJI[k],
                "label": Reaction.Kind(k).label,
                "count": counts.get(k, 0),
                "mine": k in mine,
            }
            for k in KINDS
        ],
    }


def reaction_bars(person, thread, posts):
    """Barras de reacciones del hilo y de cada mensaje con 2 consultas, sin importar cuántos haya."""
    post_ids = [p.pk for p in posts]
    rows = Reaction.objects.filter(Q(thread=thread) | Q(post__in=post_ids))
    counts, mine = {}, {}
    for key_t, key_p, kind, n in rows.values_list("thread_id", "post_id", "kind").annotate(
        n=Count("id")
    ):
        counts.setdefault(key_t or f"p{key_p}", {})[kind] = n
    for key_t, key_p, kind in rows.filter(person=person).values_list(
        "thread_id", "post_id", "kind"
    ):
        mine.setdefault(key_t or f"p{key_p}", set()).add(kind)
    thread_bar = _bar(
        counts.get(thread.pk, {}),
        mine.get(thread.pk, set()),
        thread.author_id != person.pk and is_open_to_opinion(thread),
    )
    post_bars = {
        p.pk: _bar(
            counts.get(f"p{p.pk}", {}),
            mine.get(f"p{p.pk}", set()),
            p.author_id != person.pk and not p.is_hidden and not thread.is_hidden,
        )
        for p in posts
    }
    return thread_bar, post_bars


def thread_summaries(threads):
    """{id del hilo: [(emoji, cantidad)]} para la lista, con una sola consulta."""
    ids = [t.pk for t in threads]
    out = {}
    rows = (
        Reaction.objects.filter(thread__in=ids)
        .values_list("thread_id", "kind")
        .annotate(n=Count("id"))
    )
    for thread_id, kind, n in rows:
        out.setdefault(thread_id, {})[kind] = n
    return {
        tid: [(Reaction.EMOJI[k], by_kind[k]) for k in KINDS if k in by_kind]
        for tid, by_kind in out.items()
    }


@transaction.atomic
def clear_reactions(obj, by):
    """Un responsable limpia las reacciones de contenido oculto o borrado."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede moderar.")
    if is_open_to_opinion(obj):
        raise ValueError("Solo se limpian reacciones de contenido oculto.")
    resync_xp(obj)
    deleted, _ = _reactions_of(obj).delete()
    moderation.log(by, "clear_reactions", obj, f"{deleted} reacciones")
    return deleted


# --- encuestas rápidas ----------------------------------------------------------------------------------------------


def parse_options(raw) -> list:
    """Una opción por línea; entre 2 y 6, sin repetidas, de hasta 80 caracteres. Vacío = sin encuesta."""
    if isinstance(raw, str):
        raw = raw.splitlines()
    options, seen = [], set()
    for line in raw:
        text = " ".join((line or "").split())
        if not text or text.casefold() in seen:
            continue
        if len(text) > OPTION_MAX:
            raise ValueError(f"Cada opción admite hasta {OPTION_MAX} caracteres.")
        seen.add(text.casefold())
        options.append(text)
    if options and not POLL_MIN <= len(options) <= POLL_MAX:
        raise ValueError(f"La encuesta lleva entre {POLL_MIN} y {POLL_MAX} opciones distintas.")
    return options


def supports_poll(thread) -> bool:
    return thread.category.slug == POLL_CATEGORY


@transaction.atomic
def add_poll(thread, by, options):
    """Agrega la encuesta (una sola vez) a un hilo de «Ideas y mejoras». Quien lo abrió o un responsable."""
    if by.pk != thread.author_id and not by.is_lead:
        raise PermissionError("Solo quien abrió el hilo o un responsable agrega la encuesta.")
    if not supports_poll(thread):
        raise ValueError("Las encuestas son solo para «Ideas y mejoras».")
    if thread.is_closed or thread.is_hidden:
        raise ValueError("El hilo no admite una encuesta nueva.")
    if thread.poll_options.exists():
        raise ValueError("Este hilo ya tiene encuesta.")
    options = parse_options(options)
    if not options:
        raise ValueError(f"Escribe entre {POLL_MIN} y {POLL_MAX} opciones, una por línea.")
    PollOption.objects.bulk_create(
        [PollOption(thread=thread, text=t, position=i) for i, t in enumerate(options)]
    )


@transaction.atomic
def vote(thread, person, option_id):
    """Un voto por persona; se puede cambiar mientras el hilo esté abierto."""
    if thread.is_hidden:
        raise ValueError("El hilo no está disponible.")
    if thread.is_closed:
        raise ValueError("La encuesta está cerrada.")
    try:
        option = thread.poll_options.filter(pk=int(option_id)).first()
    except (TypeError, ValueError):
        option = None
    if option is None:
        raise ValueError("Elige una de las opciones.")
    PollVote.objects.update_or_create(thread=thread, person=person, defaults={"option": option})


@transaction.atomic
def retract_vote(thread, person):
    if thread.is_closed:
        raise ValueError("La encuesta está cerrada.")
    PollVote.objects.filter(thread=thread, person=person).delete()


def poll_context(thread, person):
    """Opciones con votos y porcentaje (2 consultas), o None si el hilo no tiene encuesta."""
    options = list(thread.poll_options.annotate(n=Count("votes")))
    if not options:
        return None
    total = sum(o.n for o in options)
    mine = (
        PollVote.objects.filter(thread=thread, person=person)
        .values_list("option_id", flat=True)
        .first()
    )
    return {
        "options": [
            {
                "id": o.pk,
                "text": o.text,
                "n": o.n,
                "pct": round(100 * o.n / total) if total else 0,
                "mine": o.pk == mine,
            }
            for o in options
        ],
        "total": total,
        "mine": mine,
        "open": not thread.is_closed and not thread.is_hidden,
    }


@transaction.atomic
def clear_votes(thread, by):
    """Un responsable limpia los votos de la encuesta de un hilo oculto."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede moderar.")
    if not thread.is_hidden:
        raise ValueError("Solo se limpian votos de hilos ocultos.")
    deleted, _ = PollVote.objects.filter(thread=thread).delete()
    moderation.log(by, "clear_votes", thread, f"{deleted} votos")
    return deleted
