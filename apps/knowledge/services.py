"""Conocimiento y mejoras (Bloque 11)."""

from django.db import transaction
from django.db.models import Q

from apps.accounts.models import PersonStatus
from apps.community.models import Thread
from apps.notifications import services as notifications

from .models import BODY_MAX, TEXT_MAX, TITLE_MAX, Article, Improvement


def _clean(value, limit, what, *, required=True):
    value = (value or "").strip()
    if required and not value:
        raise ValueError(f"Escribe {what}.")
    if len(value) > limit:
        raise ValueError(f"{what.capitalize()} admite hasta {limit} caracteres.")
    return value


# --- artículos -------------------------------------------------------------------------------------------------------


def can_view(person, article) -> bool:
    return article.is_published or article.author_id == person.pk or person.is_lead


def can_edit(person, article) -> bool:
    return article.author_id == person.pk or person.is_lead


def visible(person):
    qs = Article.objects.select_related("author")
    return qs if person.is_lead else qs.filter(Q(is_published=True) | Q(author=person))


def listing(person, *, kind="", discipline=None, q=""):
    qs = visible(person).prefetch_related("disciplines")
    if kind in Article.Kind.values:
        qs = qs.filter(kind=kind)
    if discipline is not None:
        qs = qs.filter(disciplines=discipline)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    return qs.distinct()


def _article_fields(title, body, kind):
    if kind not in Article.Kind.values:
        raise ValueError("Tipo de artículo desconocido.")
    return {
        "title": _clean(title, TITLE_MAX, "un título"),
        "body": _clean(body, BODY_MAX, "el contenido"),
        "kind": kind,
    }


@transaction.atomic
def create_article(author, *, title, body, kind, disciplines=(), source_thread=None, publish=False):
    article = Article.objects.create(
        author=author,
        source_thread=source_thread,
        is_published=bool(publish),
        **_article_fields(title, body, kind),
    )
    article.disciplines.set(disciplines)
    return article


@transaction.atomic
def update_article(article, by, *, title, body, kind, disciplines=(), publish=None):
    if not can_edit(by, article):
        raise PermissionError("Solo quien escribió el artículo o un responsable puede editarlo.")
    for key, value in _article_fields(title, body, kind).items():
        setattr(article, key, value)
    if publish is not None:
        article.is_published = bool(publish)
    article.save()
    article.disciplines.set(disciplines)
    return article


def set_published(article, by, published: bool):
    if not can_edit(by, article):
        raise PermissionError("Solo quien escribió el artículo o un responsable puede publicarlo.")
    article.is_published = published
    article.save(update_fields=["is_published", "updated_at"])


def delete_article(article, by):
    if not can_edit(by, article):
        raise PermissionError("Solo quien escribió el artículo o un responsable puede eliminarlo.")
    article.delete()


def draft_from_thread(thread, by):
    """Texto inicial de un artículo a partir de una consulta resuelta. Lanza ValueError/PermissionError."""
    if thread.is_hidden:
        raise ValueError("Ese hilo no está disponible.")
    if thread.kind != Thread.Kind.QUESTION or thread.accepted_post_id is None:
        raise ValueError("Solo una consulta con respuesta aceptada se convierte en artículo.")
    if not (by.is_lead or thread.author_id == by.pk):
        raise PermissionError(
            "Solo quien abrió la consulta o un responsable la convierte en artículo."
        )
    answer = thread.accepted_post
    if answer.is_hidden or answer.is_deleted:
        raise ValueError("La respuesta aceptada ya no está disponible.")
    body = f"## Pregunta\n\n{thread.body}\n\n## Respuesta\n\n{answer.body}"
    return {"title": thread.title[:TITLE_MAX], "body": body[:BODY_MAX], "kind": Article.Kind.FAQ}


# --- mejoras -----------------------------------------------------------------------------------------------------------


def stage_order():
    return [value for value, _ in Improvement.Stage.choices]


def board():
    """Mejoras agrupadas por etapa, en el orden Idea → Plan → Ejecución → Resultado."""
    columns = {value: [] for value in stage_order()}
    for imp in Improvement.objects.select_related("proposed_by", "owner"):
        columns[imp.stage].append(imp)
    return [
        {"stage": value, "label": label, "items": columns[value]}
        for value, label in Improvement.Stage.choices
    ]


def propose(person, title, description):
    return Improvement.objects.create(
        proposed_by=person,
        title=_clean(title, TITLE_MAX, "un título"),
        description=_clean(description, TEXT_MAX, "la descripción"),
    )


def can_edit_improvement(person, imp) -> bool:
    return person.is_lead or (
        imp.proposed_by_id == person.pk and imp.stage == Improvement.Stage.IDEA
    )


@transaction.atomic
def update_improvement(imp, by, *, title, description):
    if not can_edit_improvement(by, imp):
        raise PermissionError(
            "Solo quien la propuso (mientras es una idea) o un responsable puede editarla."
        )
    imp.title = _clean(title, TITLE_MAX, "un título")
    imp.description = _clean(description, TEXT_MAX, "la descripción")
    imp.save(update_fields=["title", "description", "updated_at"])
    return imp


@transaction.atomic
def move(imp, by, *, stage, owner=None, outcome=""):
    """Un responsable cambia la etapa. Para llegar a *Resultado* hay que contar qué se logró."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable cambia la etapa de una mejora.")
    if stage not in Improvement.Stage.values:
        raise ValueError("Etapa desconocida.")
    outcome = _clean(outcome, TEXT_MAX, "el resultado", required=stage == Improvement.Stage.RESULT)
    if owner is not None and owner.status != PersonStatus.APPROVED:
        raise ValueError("La persona responsable debe estar aprobada.")
    changed = stage != imp.stage
    imp.stage, imp.owner, imp.outcome = stage, owner, outcome
    imp.save(update_fields=["stage", "owner", "outcome", "updated_at"])
    if changed and imp.proposed_by_id != by.pk:
        notifications.notify(
            imp.proposed_by,
            "improvement_stage",
            f"Tu propuesta «{imp.title}» pasó a {imp.get_stage_display()}",
            url=f"/conocimiento/mejoras/{imp.pk}/",
            key=f"improvement:{imp.pk}:{stage}:{imp.updated_at.timestamp():.6f}",
        )
    return imp


def delete_improvement(imp, by):
    if not can_edit_improvement(by, imp):
        raise PermissionError(
            "Solo quien la propuso (mientras es una idea) o un responsable puede eliminarla."
        )
    imp.delete()
