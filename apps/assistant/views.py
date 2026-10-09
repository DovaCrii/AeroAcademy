from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.community.models import Thread

from . import context, faq, quick, services
from . import search as search_module
from .search import HELP_DIR


def _ctx(request, answer=None, question="", extra=None):
    ctx = {
        "teo": {"enabled": services.enabled(), "remaining": services.remaining(request.user)},
        "shortcuts": quick.SHORTCUTS,
        "answer": answer,
        "question": question,
    }
    if (
        answer is not None
        and answer.status in ("ok", "error")
        and question
        and not request.POST.get("atajo")
    ):
        ctx["ask_forum"] = (
            reverse("community:thread_new") + "?" + urlencode(services.forum_prefill(question))
        )
    if extra:
        ctx.update(extra)
    return ctx


@require_http_methods(["GET", "POST"])
def page(request):
    """Teo en una página completa (funciona sin JavaScript)."""
    if request.method == "POST":
        answer, question = _respond(request)
        return render(request, "assistant/page.html", _ctx(request, answer, question))
    return render(request, "assistant/page.html", _ctx(request))


@require_POST
def ask(request):
    """Fragmento HTML con la respuesta, para el widget de la esquina."""
    answer, question = _respond(request)
    return render(request, "assistant/_answer.html", _ctx(request, answer, question))


def _respond(request):
    """Un atajo (local, sin el modelo) o una pregunta libre."""
    key = request.POST.get("atajo", "")
    if key:
        return quick.answer(request.user, key), quick.label(key)
    question = request.POST.get("question", "")
    return services.answer(request.user, question), question


@require_POST
def summarize(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if thread.is_hidden and not request.user.is_lead:
        raise Http404
    posts = list(thread.posts.filter(is_deleted=False, is_hidden=False))
    extra = context.thread_text(thread, posts)
    answer = services.answer(
        request.user,
        f"Resume en pocas líneas el hilo «{thread.title}».",
        extra=extra,
        kind="summary",
    )
    return render(
        request,
        "assistant/page.html",
        _ctx(request, answer, f"Resumen del hilo «{thread.title}»", {"thread": thread}),
    )


def help_page(request, slug):
    path = HELP_DIR / f"{slug}.md"
    if not slug.replace("-", "").isalnum() or not path.is_file():
        raise Http404
    text = path.read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").strip()
    return render(
        request, "assistant/help.html", {"title": title, "paragraphs": text.splitlines()[1:]}
    )


HELP_KINDS = {"help", "path", "glossary", "resource", "article", "document"}


def help_index(request):
    query = request.GET.get("q", "").strip()[:100]
    faq_hits, guide_hits = faq.search(query) if query else ([], [])
    results = (
        [h for h in search_module.search(query, limit=12) if h["kind"] in HELP_KINDS]
        if query
        else []
    )
    return render(
        request,
        "assistant/help_index.html",
        {
            "topics": faq.topics(),
            "items": faq.guides(),
            "q": query,
            "faq_hits": faq_hits,
            "guide_hits": guide_hits,
            "results": results,
            "no_results": bool(query) and not (faq_hits or guide_hits or results),
            "awake": services.enabled(),
        },
    )
