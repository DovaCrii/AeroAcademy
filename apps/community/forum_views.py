from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Discipline
from apps.paths import services as path_services

from . import forum, opinions
from .models import Category, Post, Thread

PAGE_SIZE = 20


def _categories():
    return Category.objects.filter(retired=False)


@require_http_methods(["GET"])
def index(request):
    p = request.GET
    sort = p.get("orden", "recientes")
    if sort not in dict(forum.SORTS):
        sort = "recientes"
    category = _categories().filter(slug=p.get("categoria", "")).first()
    discipline = Discipline.objects.filter(slug=p.get("disciplina", "")).first()
    page = Paginator(
        forum.listing(
            category=category,
            kind=p.get("tipo", ""),
            discipline=discipline,
            state=p.get("estado", ""),
            q=p.get("q", "").strip()[:100],
            show_hidden=request.user.is_lead,
            sort=sort,
        ),
        PAGE_SIZE,
    ).get_page(p.get("pagina"))
    page.object_list = list(page.object_list)
    summaries = opinions.thread_summaries(page.object_list)
    for t in page.object_list:
        t.reaction_summary = summaries.get(t.pk, [])
        t.can_opine = t.category.slug == opinions.POLL_CATEGORY and not t.is_closed
    query = request.GET.copy()
    query.pop("pagina", None)
    nosort = query.copy()
    nosort.pop("orden", None)
    return render(
        request,
        "community/forum_index.html",
        {
            "page": page,
            "categories": _categories(),
            "disciplines": Discipline.objects.all(),
            "kinds": Thread.Kind.choices,
            "f": {k: p.get(k, "") for k in ("categoria", "disciplina", "tipo", "estado", "q")},
            "sort": sort,
            "qs_nosort": nosort.urlencode(),
            "sorts": forum.SORTS,
            "qs": query.urlencode(),
            "paths": path_services.visible_paths(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def new(request):
    categories = _categories()
    if request.method == "POST":
        category = categories.filter(slug=request.POST.get("category", "")).first()
        disciplines = Discipline.objects.filter(slug__in=request.POST.getlist("disciplines"))
        try:
            if category is None:
                raise ValueError("Elige una categoría.")
            thread = forum.create_thread(
                request.user,
                category,
                request.POST.get("kind", ""),
                request.POST.get("title", ""),
                request.POST.get("body", ""),
                disciplines,
                request.POST.get("poll_options", ""),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Hilo publicado.")
            return redirect("community:thread", pk=thread.pk)
    return render(
        request,
        "community/thread_new.html",
        {
            "categories": categories,
            "disciplines": Discipline.objects.all(),
            "kinds": Thread.Kind.choices,
            "poll_category": opinions.POLL_CATEGORY,
            "v": request.POST
            or {
                "title": request.GET.get("titulo", "")[:150],
                "body": request.GET.get("detalle", "")[:5000],
            },
        },
    )


@require_http_methods(["GET", "POST"])
def thread_detail(request, pk):
    thread = get_object_or_404(
        Thread.objects.select_related("author", "category", "accepted_post__author"), pk=pk
    )
    if thread.is_hidden and not request.user.is_lead:
        raise Http404
    if request.method == "POST":
        try:
            forum.reply(thread, request.user, request.POST.get("body", ""))
            messages.success(request, "Respuesta publicada.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("community:thread", pk=thread.pk)
    posts = thread.posts.filter(is_deleted=False).select_related("author")
    if not request.user.is_lead:
        posts = posts.filter(is_hidden=False)
    posts = list(posts)
    thread_bar, post_bars = opinions.reaction_bars(request.user, thread, posts)
    for post in posts:
        post.bar = post_bars[post.pk]
    poll = opinions.poll_context(thread, request.user)
    return render(
        request,
        "community/thread.html",
        {
            "thread": thread,
            "posts": posts,
            "can_manage": forum.can_manage(request.user, thread),
            "disciplines": thread.disciplines.all(),
            "categories": _categories(),
            "thread_bar": thread_bar,
            "poll": poll,
            "can_add_poll": poll is None
            and opinions.supports_poll(thread)
            and not thread.is_closed
            and (request.user.pk == thread.author_id or request.user.is_lead),
            "is_idea": opinions.supports_poll(thread),
        },
    )


def _guard(request, fn, *args):
    try:
        fn(*args)
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
        return False
    return True


@require_POST
def accept(request, pk, post_pk):
    thread = get_object_or_404(Thread, pk=pk)
    post = get_object_or_404(Post, pk=post_pk, thread=thread)
    if _guard(request, forum.accept, thread, post, request.user):
        messages.success(request, "Respuesta marcada como aceptada.")
    return redirect("community:thread", pk=pk)


@require_POST
def unaccept(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    _guard(request, forum.unaccept, thread, request.user)
    return redirect("community:thread", pk=pk)


@require_POST
def toggle_closed(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    _guard(request, forum.set_closed, thread, request.user, not thread.is_closed)
    return redirect("community:thread", pk=pk)


@require_POST
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk, is_deleted=False)
    if _guard(request, forum.delete_post, post, request.user):
        messages.success(request, "Mensaje eliminado.")
    return redirect(reverse("community:thread", args=[post.thread_id]))


def _visible_thread(request, pk):
    thread = get_object_or_404(Thread.objects.select_related("category"), pk=pk)
    if thread.is_hidden and not request.user.is_lead:
        raise Http404
    return thread


@require_POST
def react(request, kind, pk):
    """Pone o quita una reacción a un hilo (`kind` = thread) o a un mensaje (`kind` = post)."""
    if kind == "post":
        post = get_object_or_404(Post.objects.select_related("thread"), pk=pk)
        thread, target, anchor = _visible_thread(request, post.thread_id), post, f"#post-{pk}"
    elif kind == "thread":
        thread = target = _visible_thread(request, pk)
        anchor = "#opinar"
    else:
        raise Http404
    try:
        opinions.toggle_reaction(request.user, target, request.POST.get("reaction", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("community:thread", args=[thread.pk]) + anchor)


@require_POST
def poll_vote(request, pk):
    thread = _visible_thread(request, pk)
    try:
        if request.POST.get("action") == "retract":
            opinions.retract_vote(thread, request.user)
        else:
            opinions.vote(thread, request.user, request.POST.get("option"))
            messages.success(
                request, "Voto registrado. Puedes cambiarlo mientras el hilo esté abierto."
            )
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("community:thread", args=[pk]) + "#encuesta")


@require_POST
def poll_add(request, pk):
    thread = _visible_thread(request, pk)
    if _guard(
        request, opinions.add_poll, thread, request.user, request.POST.get("poll_options", "")
    ):
        messages.success(request, "Encuesta agregada.")
    return redirect(reverse("community:thread", args=[pk]) + "#encuesta")
