from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from . import services


def _page(request, cfg, *, unsaved=False):
    return render(
        request,
        "gamification/avatar_editor.html",
        {
            "cfg": cfg,
            "sections": services.editor_sections(cfg, request.user),
            "preview": services.svg_sized(
                cfg, 192, title=f"Avatar de {request.user.name}", view="full"
            ),
            "unsaved": unsaved,
        },
    )


@require_http_methods(["GET", "POST"])
def avatar_editor(request):
    """Editor del avatar: todo es opcional y se puede cambiar cuando se quiera."""
    if request.method == "POST":
        services.save_config(request.user, request.POST)
        messages.success(request, "Tu avatar quedó guardado.")
        return redirect("gamification:avatar_editor")
    if request.GET.get("azar"):
        return _page(request, services.random_config(request.user), unsaved=True)
    if request.GET.get("restablecer"):
        from . import avatar

        cfg = avatar.clean_config(
            avatar.default_config(request.user.login, request.user.character_class),
            unlocked=services.unlocked_badges(request.user),
        )
        return _page(request, cfg, unsaved=True)
    return _page(request, services.person_config(request.user))


@require_GET
def avatar_preview(request):
    """Vista previa en vivo: solo el fragmento; no guarda nada."""
    cfg = services.clean_from_form(request.user, request.GET)
    return render(
        request,
        "gamification/_preview.html",
        {
            "big": services.svg_sized(
                cfg, 192, title=f"Avatar de {request.user.name}", view="full"
            ),
            "medium": services.svg_sized(cfg, 96, view="full"),
            "small": services.svg_sized(cfg, 64, view="full"),
            "bust": services.svg_sized(cfg, 32, view="bust"),
        },
    )
