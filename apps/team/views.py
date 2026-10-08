from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.paths import services as path_services
from apps.paths.models import SharedItem

from . import services


@require_GET
def board(request):
    expiring, expired = services.expiry_lists(request.user)
    return render(
        request,
        "team/board.html",
        {
            "table": services.progress_table(request.user),
            "notes": services.recent_notes(request.user),
            "credentials": services.recent_credentials(request.user),
            "expiring": expiring,
            "expired": expired,
            "kit_paths": services.kit_paths(request.user),
        },
    )


@require_GET
def matrix(request):
    return render(
        request,
        "team/matrix.html",
        {
            "m": services.matrix(request.user, request.GET.get("atributo", "")),
            "attributes": services.ATTRIBUTES,
        },
    )


def _path_or_404(request, slug):
    path = path_services.visible_paths(request.user).filter(slug=slug).first()
    if path is None:
        raise Http404
    return path


@require_GET
def kit(request, slug):
    path = _path_or_404(request, slug)
    return render(request, "team/kit.html", {"path": path, **services.kit_and_plan(path)})


@require_POST
def toggle(request, slug, key):
    path = _path_or_404(request, slug)
    item = get_object_or_404(SharedItem, path=path, key=key)
    try:
        services.set_shared(item, request.user, request.POST.get("checked") == "1")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect(f"/equipo/kit/{slug}/#{key}")
