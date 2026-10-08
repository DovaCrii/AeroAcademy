from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import Person, PersonStatus
from apps.catalog.models import Discipline
from apps.community.models import Thread

from . import services
from .models import Article, Improvement

PAGE_SIZE = 20


def _article_or_404(request, pk):
    article = get_object_or_404(Article.objects.select_related("author", "source_thread"), pk=pk)
    if not services.can_view(request.user, article):
        raise Http404
    return article


def _ctx_form(**extra):
    return {"kinds": Article.Kind.choices, "disciplines": Discipline.objects.all(), **extra}


@require_GET
def index(request):
    p = request.GET
    discipline = Discipline.objects.filter(slug=p.get("disciplina", "")).first()
    page = Paginator(
        services.listing(
            request.user,
            kind=p.get("tipo", ""),
            discipline=discipline,
            q=p.get("q", "").strip()[:100],
        ),
        PAGE_SIZE,
    ).get_page(p.get("pagina"))
    query = p.copy()
    query.pop("pagina", None)
    return render(
        request,
        "knowledge/index.html",
        {
            "page": page,
            "kinds": Article.Kind.choices,
            "disciplines": Discipline.objects.all(),
            "f": {k: p.get(k, "") for k in ("q", "tipo", "disciplina")},
            "qs": query.urlencode(),
        },
    )


@require_http_methods(["GET", "POST"])
def new(request):
    thread = None
    initial = {}
    thread_id = request.GET.get("hilo") or request.POST.get("thread")
    if thread_id and thread_id.isdigit():
        thread = get_object_or_404(Thread, pk=int(thread_id))
        if thread.is_hidden and not request.user.is_lead:
            raise Http404  # no se revela que existe
        try:
            initial = services.draft_from_thread(thread, request.user)
        except PermissionError as exc:
            messages.error(request, str(exc))
            return redirect("community:thread", pk=thread.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("community:thread", pk=thread.pk)
    if request.method == "POST":
        disciplines = Discipline.objects.filter(slug__in=request.POST.getlist("disciplines"))
        try:
            article = services.create_article(
                request.user,
                title=request.POST.get("title", ""),
                body=request.POST.get("body", ""),
                kind=request.POST.get("kind", ""),
                disciplines=disciplines,
                source_thread=thread,
                publish=request.POST.get("publish") == "on",
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Artículo guardado.")
            return redirect("knowledge:detail", pk=article.pk)
    return render(
        request,
        "knowledge/form.html",
        _ctx_form(v=request.POST or initial, editing=False, thread=thread),
    )


@require_GET
def detail(request, pk):
    article = _article_or_404(request, pk)
    return render(
        request,
        "knowledge/detail.html",
        {
            "a": article,
            "disciplines": article.disciplines.all(),
            "can_edit": services.can_edit(request.user, article),
        },
    )


@require_http_methods(["GET", "POST"])
def edit(request, pk):
    article = _article_or_404(request, pk)
    if not services.can_edit(request.user, article):
        raise Http404
    if request.method == "POST":
        try:
            services.update_article(
                article,
                request.user,
                title=request.POST.get("title", ""),
                body=request.POST.get("body", ""),
                kind=request.POST.get("kind", ""),
                disciplines=Discipline.objects.filter(slug__in=request.POST.getlist("disciplines")),
                publish=request.POST.get("publish") == "on",
            )
        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Artículo actualizado.")
            return redirect("knowledge:detail", pk=article.pk)
    initial = {
        "title": article.title,
        "body": article.body,
        "kind": article.kind,
        "publish": "on" if article.is_published else "",
    }
    return render(
        request,
        "knowledge/form.html",
        _ctx_form(
            v=request.POST or initial,
            editing=True,
            a=article,
            chosen=[d.slug for d in article.disciplines.all()],
        ),
    )


@require_POST
def publish(request, pk):
    article = _article_or_404(request, pk)
    try:
        services.set_published(article, request.user, request.POST.get("published") == "1")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect("knowledge:detail", pk=pk)


@require_POST
def delete(request, pk):
    article = _article_or_404(request, pk)
    try:
        services.delete_article(article, request.user)
    except PermissionError as exc:
        messages.error(request, str(exc))
        return redirect("knowledge:detail", pk=pk)
    messages.success(request, "Artículo eliminado.")
    return redirect("knowledge:index")


# --- mejoras ---------------------------------------------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def improvements(request):
    if request.method == "POST":
        try:
            imp = services.propose(
                request.user, request.POST.get("title", ""), request.POST.get("description", "")
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Propuesta enviada.")
            return redirect("knowledge:improvement", pk=imp.pk)
    return render(request, "knowledge/board.html", {"columns": services.board(), "v": request.POST})


@require_http_methods(["GET", "POST"])
def improvement(request, pk):
    imp = get_object_or_404(Improvement.objects.select_related("proposed_by", "owner"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "move":
                owner = Person.objects.filter(
                    pk=request.POST.get("owner") or 0, status=PersonStatus.APPROVED
                ).first()
                services.move(
                    imp,
                    request.user,
                    stage=request.POST.get("stage", ""),
                    owner=owner,
                    outcome=request.POST.get("outcome", ""),
                )
                messages.success(request, "Etapa actualizada.")
            elif action == "edit":
                services.update_improvement(
                    imp,
                    request.user,
                    title=request.POST.get("title", ""),
                    description=request.POST.get("description", ""),
                )
                messages.success(request, "Propuesta actualizada.")
            elif action == "delete":
                services.delete_improvement(imp, request.user)
                messages.success(request, "Propuesta eliminada.")
                return redirect("knowledge:improvements")
        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))
        return redirect("knowledge:improvement", pk=pk)
    return render(
        request,
        "knowledge/improvement.html",
        {
            "imp": imp,
            "stages": Improvement.Stage.choices,
            "people": Person.objects.filter(status=PersonStatus.APPROVED, is_active=True)
            if request.user.is_lead
            else [],
            "can_edit": services.can_edit_improvement(request.user, imp),
        },
    )
