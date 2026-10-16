from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import Person, PersonStatus

from . import game, services
from . import sheet as sheet_data
from .avatar import engine
from .forms import SheetForm


def _page(request, cfg, *, unsaved=False):
    open_slug = services.resolve_section(request.GET.get("seccion"), request.user)
    return render(
        request,
        "gamification/avatar_editor.html",
        {
            "cfg": cfg,
            "sections": services.editor_sections(cfg, request.user, open_slug),
            "open_slug": open_slug,
            "tile_bg": engine.background_for(cfg),
            **services.preview_context(cfg, request.user),
            "unsaved": unsaved,
        },
    )


@require_http_methods(["GET", "POST"])
def avatar_editor(request):
    """Editor del avatar: todo es opcional y se puede cambiar cuando se quiera."""
    if request.method == "POST":
        services.save_config(request.user, request.POST)
        messages.success(request, "Tu avatar quedó guardado.")
        section = request.POST.get("seccion", "")
        target = reverse("gamification:avatar_editor")
        # Se vuelve a la sección que estaba abierta (el campo oculto seccion solo vale si está en la lista cerrada).
        return redirect(
            f"{target}?seccion={section}" if section in services.SECTION_SLUGS else target
        )
    if request.GET.get("azar"):
        return _page(request, services.random_config(request.user), unsaved=True)
    if request.GET.get("restablecer"):
        from . import avatar

        cfg = avatar.clean_config(
            avatar.default_config(request.user.login, request.user.character_class),
            **services.gates(request.user),
        )
        return _page(request, cfg, unsaved=True)
    return _page(request, services.person_config(request.user))


@require_GET
def avatar_preview(request):
    """Vista previa en vivo: solo el fragmento; no guarda nada."""
    cfg = services.clean_from_form(request.user, request.GET)
    return render(
        request, "gamification/_preview.html", services.preview_context(cfg, request.user)
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


# Qué desplegables empiezan abiertos en cada vista de la hoja (las tres vistas solo cambian esto y la vitrina).
OPEN_SECTIONS = {"juego": ("attrs", "badges"), "compacta": (), "pro": ("skills", "creds")}


def _render_sheet(request, person):
    stored = {"game": "juego", "compact": "compacta", "pro": "pro"}.get(person.sheet_view)
    view = request.GET.get("vista") or stored or ("juego" if person.show_game_view else "pro")
    ctx = sheet_data.build(person, request.user)
    ctx["view"] = view if view in {"pro", "compacta"} else "juego"
    ctx["open_sections"] = OPEN_SECTIONS[ctx["view"]]
    cfg = services.person_config(person)
    svg = services.svg_sized(
        cfg,
        160,
        title=f"Avatar de {person.name}",
        view="full",
        bg_alt=services.auto_background(person, cfg),
    )
    ctx["avatar_big"] = services.framed(svg, cfg, level=ctx["info"]["level"], large=True)
    if ctx[
        "is_owner"
    ]:  # «Lo que lleva» dice de dónde viene cada pieza: solo la ve su dueña (decisión Q4)
        ctx["wearing"] = services.wearing(cfg, person)
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
        if data["sheet_view"]:
            person.sheet_view = data["sheet_view"]
            person.show_game_view = data["sheet_view"] == "game"
        person.links = {k: data[k] for k in ("linkedin", "credly") if data[k]}
        person.save(
            update_fields=[
                "headline", "bio", "selected_title", "show_game_view", "sheet_view", "links", "updated_at",
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
