import re

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


# Qué tipos de ruta sabe dibujar cada mundo, y a cuál se recurre si el suyo no puede.
WORLD_KINDS = {
    "architecture": {LearningPath.Kind.STRUCTURED},
    "civil": {LearningPath.Kind.EXTERNAL_TRACK},
    "aero": {LearningPath.Kind.STRUCTURED},
}
KIND_FALLBACK_WORLD = {
    LearningPath.Kind.STRUCTURED: "architecture",
    LearningPath.Kind.EXTERNAL_TRACK: "civil",
}


def resolve_world(path):
    """Mundo con el que se dibuja la ruta (docs/MUNDOS.md), o "" para la vista genérica.

    Si el mundo no sabe mostrar ese tipo de ruta (p. ej. Civil 3D, estructurada, en el mundo civil hecho para
    Bentley) o todavía no tiene diseño (p. ej. «survey» en Topografía 101), se usa el de su tipo: nunca una ruta vacía.
    """
    world = path.world
    if world and (
        path.kind not in WORLD_KINDS.get(world, {path.kind})
        or not world_template(world, "path.html")
    ):
        world = KIND_FALLBACK_WORLD.get(path.kind, "")
    return world


def respond(request, path, level_code, step=""):
    """Respuesta parcial para el ayudante JS (`X-Partial`) o redirección para quien no tiene JS.

    `step` es el paso (`?paso=`) donde estaba la persona: se vuelve a él (misiones, preguntas…).
    """
    world = resolve_world(path)
    partial = world_template(world, "_app.html") if world else None
    if request.headers.get("X-Partial") and partial:
        ctx = services.world_context(request.user, path, level_code, step)
        return render(request, partial, ctx)
    url = reverse("paths:detail", args=[path.slug])
    paso = f"&paso={step}" if step_ok(step) else ""
    return redirect(f"{url}?nivel={level_code}{paso}#panel")


def step_ok(step):
    return isinstance(step, str) and re.fullmatch(r"[a-z0-9]{1,12}", step) is not None


@require_POST
def toggle_milestone(request, slug, key):
    path = _path_or_404(request, slug)
    milestone = get_object_or_404(Milestone, path=path, key=key, retired=False)
    services.set_milestone(request.user, milestone, request.POST.get("checked") == "1")
    return respond(request, path, milestone.level.code, "practica")


@require_POST
def answer_quiz(request, slug, key):
    path = _path_or_404(request, slug)
    question = get_object_or_404(QuizQuestion, path=path, key=key, retired=False)
    try:
        choice = int(request.POST.get("choice", ""))
        services.answer_question(request.user, question, choice)
    except ValueError:
        return HttpResponseBadRequest("Opción inválida.")
    return respond(request, path, question.level.code, "quiz")


@require_POST
def set_goal(request, slug):
    path = _path_or_404(request, slug)
    try:
        services.set_goal(request.user, path, request.POST.get("goal", ""))
    except ValueError:
        return HttpResponseBadRequest("Meta inválida.")
    return respond(request, path, request.POST.get("nivel", ""), request.POST.get("paso", ""))
