from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.community.models import Thread

from . import context, services
from .search import HELP_DIR


def _ctx(request, answer=None, question="", extra=None):
    ctx = {
        "teo": {"enabled": services.enabled(), "remaining": services.remaining(request.user)},
        "answer": answer,
        "question": question,
    }
    if answer is not None and answer.status in ("ok", "error"):
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
        question = request.POST.get("question", "")
        answer = services.answer(request.user, question)
        return render(request, "assistant/page.html", _ctx(request, answer, question))
    return render(request, "assistant/page.html", _ctx(request))


@require_POST
def ask(request):
    """Fragmento HTML con la respuesta, para el widget de la esquina."""
    question = request.POST.get("question", "")
    answer = services.answer(request.user, question)
    return render(request, "assistant/_answer.html", _ctx(request, answer, question))


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


def help_index(request):
    items = []
    for p in sorted(HELP_DIR.glob("*.md")):
        title = p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        items.append({"slug": p.stem, "title": title})
    return render(request, "assistant/help_index.html", {"items": items})
