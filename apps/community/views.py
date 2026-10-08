from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.paths import services as path_services
from apps.paths.models import Level

from . import services
from .models import Note


def _path_or_404(request, slug):
    path = path_services.visible_paths(request.user).filter(slug=slug).first()
    if path is None:
        raise Http404
    return path


def _back(request, fallback):
    target = request.POST.get("next", "")
    ok = target.startswith("/") and not target.startswith("//")
    if ok and url_has_allowed_host_and_scheme(target, {request.get_host()}):
        return target
    return fallback


@require_http_methods(["GET", "POST"])
def path_notes(request, slug):
    """Bitácora de notas de una ruta, con filtros por tipo y capítulo, y el formulario para escribir."""
    path = _path_or_404(request, slug)
    levels = list(Level.objects.filter(path=path).order_by("order"))
    if request.method == "POST":
        level = next((lv for lv in levels if lv.code == request.POST.get("level")), None)
        try:
            services.create_note(
                request.user,
                path,
                request.POST.get("text", ""),
                request.POST.get("type", ""),
                level=level,
            )
            messages.success(request, "Nota publicada.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(_back(request, reverse("community:path_notes", args=[slug])))
    kind = request.GET.get("tipo", "")
    code = request.GET.get("nivel", "")
    level = next((lv for lv in levels if lv.code == code), None)
    notes = services.with_replies(
        services.notes_for(path, level=level, type=kind if kind in services.TOP_TYPES else None)[
            :100
        ]
    )
    return render(
        request,
        "community/path_notes.html",
        {
            "path": path,
            "levels": levels,
            "notes": notes,
            "types": [(v, label) for v, label in Note.Type.choices if v in services.TOP_TYPES],
            "f": {"tipo": kind, "nivel": code},
            "max": services.NOTE_MAX,
        },
    )


@require_POST
def reply(request, pk):
    parent = get_object_or_404(Note, pk=pk, is_deleted=False)
    path = _path_or_404(request, parent.path.slug)
    try:
        services.create_note(
            request.user, path, request.POST.get("text", ""), "reply", parent=parent
        )
        messages.success(request, "Respuesta publicada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(_back(request, reverse("community:path_notes", args=[path.slug])))


@require_POST
def delete(request, pk):
    note = get_object_or_404(Note, pk=pk, is_deleted=False)
    path = _path_or_404(request, note.path.slug)
    try:
        services.delete_note(note, request.user)
        messages.success(request, "Nota eliminada.")
    except PermissionError:
        messages.error(request, "Solo quien escribió la nota puede borrarla.")
    return redirect(_back(request, reverse("community:path_notes", args=[path.slug])))
