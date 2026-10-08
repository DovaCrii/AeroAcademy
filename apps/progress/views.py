from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template import TemplateDoesNotExist
from django.template.loader import select_template
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.paths import services as path_services
from apps.paths.models import LearningPath, Milestone, QuizQuestion

from . import services


def _path_or_404(request, slug):
    path = path_services.visible_paths(request.user).filter(slug=slug).first()
    if path is None or path.kind != LearningPath.Kind.STRUCTURED:
        raise Http404
    return path


def world_template(world, name):
    """Plantilla del mundo si existe; si no, None (la ruta usa la vista genérica)."""
    try:
        return select_template([f"worlds/{world}/{name}"]).template.name
    except TemplateDoesNotExist:
        return None


def respond(request, path, level_code):
    """Respuesta parcial para el ayudante JS (`X-Partial`) o redirección para quien no tiene JS."""
    partial = world_template(path.world, "_app.html")
    if request.headers.get("X-Partial") and partial:
        ctx = services.world_context(request.user, path, level_code)
        return render(request, partial, ctx)
    url = reverse("paths:detail", args=[path.slug])
    return redirect(f"{url}?nivel={level_code}#panel")


@require_POST
def toggle_milestone(request, slug, key):
    path = _path_or_404(request, slug)
    milestone = get_object_or_404(Milestone, path=path, key=key, retired=False)
    services.set_milestone(request.user, milestone, request.POST.get("checked") == "1")
    return respond(request, path, milestone.level.code)


@require_POST
def answer_quiz(request, slug, key):
    path = _path_or_404(request, slug)
    question = get_object_or_404(QuizQuestion, path=path, key=key, retired=False)
    try:
        choice = int(request.POST.get("choice", ""))
        services.answer_question(request.user, question, choice)
    except ValueError:
        return HttpResponseBadRequest("Opción inválida.")
    return respond(request, path, question.level.code)


@require_POST
def set_goal(request, slug):
    path = _path_or_404(request, slug)
    try:
        services.set_goal(request.user, path, request.POST.get("goal", ""))
    except ValueError:
        return HttpResponseBadRequest("Meta inválida.")
    return respond(request, path, request.POST.get("nivel", ""))
