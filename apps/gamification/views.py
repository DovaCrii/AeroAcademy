from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import Person, PersonStatus

from . import game, services
from . import sheet as sheet_data
from .forms import SheetForm


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


@require_POST
def seen(request):
    """La persona vio sus celebraciones (insignias nuevas y subida de nivel)."""
    shown = [int(x) for x in request.POST.getlist("badge") if x.isdigit()]
    level = request.POST.get("level", "")
    game.mark_seen(
        request.user,
        min(int(level), game.level_info(request.user)["level"]) if level.isdigit() else None,
        shown,
    )  # solo lo que se mostró: lo ganado después sigue pendiente
    target = request.POST.get("next", "")
    ok = target.startswith("/") and not target.startswith("//")
    if not ok or not url_has_allowed_host_and_scheme(target, {request.get_host()}):
        target = "/"
    return redirect(target)


def _render_sheet(request, person):
    view = request.GET.get("vista") or ("juego" if person.show_game_view else "pro")
    ctx = sheet_data.build(person, request.user)
    ctx["view"] = "pro" if view == "pro" else "juego"
    ctx["avatar_big"] = services.svg_sized(
        services.person_config(person), 160, title=f"Avatar de {person.name}", view="full"
    )
    return render(request, "gamification/sheet.html", ctx)


def my_sheet(request):
    return _render_sheet(request, request.user)


def sheet(request, pk):
    person = get_object_or_404(Person, pk=pk, status=PersonStatus.APPROVED, is_active=True)
    return _render_sheet(request, person)


@require_http_methods(["GET", "POST"])
def edit_sheet(request):
    """Solo la persona edita su hoja (la ruta no recibe un id)."""
    person = request.user
    form = SheetForm(request.POST or None, person=person, initial=SheetForm.initial_for(person))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        person.headline, person.bio = data["headline"].strip(), data["bio"].strip()
        person.selected_title = data["selected_title"]
        person.show_game_view = data["show_game_view"]
        person.links = {k: data[k] for k in ("linkedin", "credly") if data[k]}
        if data["character_class"] != person.character_class:
            person.character_class = data["character_class"]
            if person.avatar_config and data["character_class"]:
                person.avatar_config = {**person.avatar_config, "class": data["character_class"]}
        person.save(
            update_fields=[
                "headline", "bio", "selected_title", "show_game_view", "links",
                "character_class", "avatar_config", "updated_at",
            ]
        )  # fmt: skip
        sheet_data.sync_profile(person)
        messages.success(request, "Tu hoja de personaje quedó guardada.")
        return redirect("gamification:my_sheet")
    return render(request, "gamification/sheet_edit.html", {"form": form})


def directory(request):
    """Tarjetas de personaje del equipo, en orden alfabético: no hay ranking individual (D17)."""
    people = list(
        Person.objects.filter(status=PersonStatus.APPROVED, is_active=True)
        .select_related("selected_title")
        .annotate(total=Sum("xp_events__points"))
        .order_by("display_name", "login")
    )
    game.prefetch_badges(people)
    for person in people:
        person.level = game.level_for(person.total or 0)
    return render(request, "gamification/directory.html", {"people": people})
