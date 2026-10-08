"""Índice de búsqueda FTS5 con lo que es visible para todo el equipo (docs/BOT.md).

Lista blanca de orígenes: rutas publicadas, recursos, glosarios, notas, hilos y mensajes no ocultos ni borrados, y
la ayuda. **Nada de `credentials` ni de `Person`**. Cada resultado se revalida contra la base al consultarlo, así que
algo oculto o borrado después de indexar no se entrega aunque el índice esté viejo.
"""

import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from django.db import connection, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Resource
from apps.community.models import Note, Post, Thread
from apps.knowledge.models import Article
from apps.library.models import Document
from apps.paths.models import LearningPath, PathExtra

from .models import IndexState

HELP_DIR = Path(__file__).resolve().parent / "help"
MAX_AGE = timedelta(minutes=5)
BODY_LIMIT = 1500
_WORD = re.compile(r"[\wáéíóúüñÁÉÍÓÚÜÑ]{3,}", re.UNICODE)


def _help_rows():
    for path in sorted(HELP_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
        yield (
            "help",
            f"help:{path.stem}",
            title,
            text,
            reverse("assistant:help", args=[path.stem]),
        )


def _rows():
    for p in LearningPath.objects.filter(is_published=True):
        yield (
            "path",
            f"path:{p.pk}",
            p.title,
            p.description,
            reverse("paths:detail", args=[p.slug]),
        )
        for extra in p.extras.filter(kind=PathExtra.Kind.GLOSSARY):
            d = extra.data or {}
            if d.get("term"):
                yield (
                    "glossary",
                    f"glossary:{extra.pk}",
                    d["term"],
                    f"{d.get('meaning', '')} {d.get('location', '')}".strip(),
                    reverse("paths:detail", args=[p.slug]),
                )
    for r in Resource.objects.prefetch_related("skills", "products").all():
        url = reverse("catalog:resources") + "?q=" + quote(r.title)
        tags = ", ".join([s.name for s in r.skills.all()] + [p.name for p in r.products.all()])
        body = f"{r.description} {('Habilidades y productos: ' + tags) if tags else ''}".strip()
        yield ("resource", f"resource:{r.pk}", r.title, body, url)
    visible_notes = Note.objects.filter(
        is_deleted=False, is_hidden=False, path__is_published=True
    ).exclude(Q(parent__is_deleted=True) | Q(parent__is_hidden=True))
    for n in visible_notes.select_related("path"):
        yield (
            "note",
            f"note:{n.pk}",
            f"Nota ({n.get_type_display()})",
            n.text,
            reverse("community:path_notes", args=[n.path.slug]),
        )
    for t in Thread.objects.filter(is_hidden=False):
        yield (
            "thread",
            f"thread:{t.pk}",
            t.title,
            t.body,
            reverse("community:thread", args=[t.pk]),
        )
    for p in Post.objects.filter(
        is_deleted=False, is_hidden=False, thread__is_hidden=False
    ).select_related("thread"):
        yield (
            "post",
            f"post:{p.pk}",
            p.thread.title,
            p.body,
            reverse("community:thread", args=[p.thread_id]) + f"#post-{p.pk}",
        )
    for a in Article.objects.filter(is_published=True):
        yield (
            "article",
            f"article:{a.pk}",
            a.title,
            a.body,
            reverse("knowledge:detail", args=[a.pk]),
        )
    for d in Document.objects.filter(is_restricted=False):
        body = f"{d.get_doc_type_display()}. {d.description} {' '.join(d.tags or [])}".strip()
        yield (
            "document",
            f"document:{d.pk}",
            d.title,
            body,
            reverse("library:detail", args=[d.pk]),
        )
    yield from _help_rows()


@transaction.atomic
def reindex():
    rows = [(k, ref, title, (body or "")[:BODY_LIMIT], url) for k, ref, title, body, url in _rows()]
    with connection.cursor() as cur:
        cur.execute("DELETE FROM assistant_fts")
        cur.executemany(
            "INSERT INTO assistant_fts (kind, ref, title, body, url) VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    IndexState.objects.all().delete()
    IndexState.objects.create(built_at=timezone.now(), rows=len(rows))
    return len(rows)


def ensure_fresh():
    state = IndexState.objects.first()
    if state is None or timezone.now() - state.built_at > MAX_AGE:
        reindex()


def _fts_query(text):
    words = []
    for w in _WORD.findall(text or ""):
        w = w.lower()
        if w not in words:
            words.append(w)
    return " OR ".join(f'"{w}"' for w in words[:8])


def _still_visible(ref):
    kind, _, pk = ref.partition(":")
    pk = int(pk) if pk.isdigit() else 0
    if kind == "note":
        return (
            Note.objects.filter(pk=pk, is_deleted=False, is_hidden=False, path__is_published=True)
            .exclude(Q(parent__is_deleted=True) | Q(parent__is_hidden=True))
            .exists()
        )
    if kind == "glossary":
        return PathExtra.objects.filter(pk=pk, path__is_published=True).exists()
    if kind == "thread":
        return Thread.objects.filter(pk=pk, is_hidden=False).exists()
    if kind == "post":
        return Post.objects.filter(
            pk=pk, is_deleted=False, is_hidden=False, thread__is_hidden=False
        ).exists()
    if kind == "document":
        return Document.objects.filter(pk=pk, is_restricted=False).exists()
    if kind == "article":
        return Article.objects.filter(pk=pk, is_published=True).exists()
    if kind == "path":
        return LearningPath.objects.filter(pk=pk, is_published=True).exists()
    return True


def search(text, limit=6):
    """Mejores resultados: lista de dicts {kind, title, body, url}."""
    query = _fts_query(text)
    if not query:
        return []
    ensure_fresh()
    with connection.cursor() as cur:
        cur.execute(
            "SELECT kind, ref, title, body, url FROM assistant_fts WHERE assistant_fts MATCH %s "
            "ORDER BY rank LIMIT %s",
            [query, limit * 3],
        )
        found = cur.fetchall()
    out = []
    for kind, ref, title, body, url in found:
        if _still_visible(ref):
            out.append({"kind": kind, "title": title, "body": body, "url": url})
        if len(out) >= limit:
            break
    return out
