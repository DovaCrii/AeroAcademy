from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Discipline
from apps.paths import services as path_services

from . import forum
from .models import Category, Post, Thread

PAGE_SIZE = 20


def _categories():
    return Category.objects.filter(retired=False)


@require_http_methods(["GET"])
def index(request):
    p = request.GET
    category = _categories().filter(slug=p.get("categoria", "")).first()
    discipline = Discipline.objects.filter(slug=p.get("disciplina", "")).first()
    page = Paginator(
        forum.listing(
            category=category,
            kind=p.get("tipo", ""),
            discipline=discipline,
            state=p.get("estado", ""),
            q=p.get("q", "").strip()[:100],
        ),
        PAGE_SIZE,
    ).get_page(p.get("pagina"))
    query = request.GET.copy()
    query.pop("pagina", None)
    return render(
        request,
        "community/forum_index.html",
        {
            "page": page,
            "categories": _categories(),
            "disciplines": Discipline.objects.all(),
            "kinds": Thread.Kind.choices,
            "f": {k: p.get(k, "") for k in ("categoria", "disciplina", "tipo", "estado", "q")},
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
            "v": request.POST,
        },
    )


@require_http_methods(["GET", "POST"])
def thread_detail(request, pk):
    thread = get_object_or_404(
        Thread.objects.select_related("author", "category", "accepted_post__author"), pk=pk
    )
    if request.method == "POST":
        try:
            forum.reply(thread, request.user, request.POST.get("body", ""))
            messages.success(request, "Respuesta publicada.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("community:thread", pk=thread.pk)
    posts = list(thread.posts.filter(is_deleted=False).select_related("author"))
    return render(
        request,
        "community/thread.html",
        {
            "thread": thread,
            "posts": posts,
            "can_manage": forum.can_manage(request.user, thread),
            "disciplines": thread.disciplines.all(),
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
