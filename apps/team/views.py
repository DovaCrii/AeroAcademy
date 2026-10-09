from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import Person
from apps.catalog.models import Discipline
from apps.paths import services as path_services
from apps.paths.models import SharedItem

from . import onboarding, services


@require_GET
def board(request):
    expiring, expired = services.expiry_lists(request.user)
    return render(
        request,
        "team/board.html",
        {
            "areas": onboarding.board_areas(),
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


# --- incorporación del equipo (solo responsables) ---------------------------------------------------------------


def _lead_only(request):
    if not request.user.is_lead:
        raise PermissionDenied


def _admin_only(request):
    """Agregar personas, enlaces de registro y cambios de rol son solo del admin (D34)."""
    if not request.user.is_admin:
        raise PermissionDenied


@require_GET
def people(request):
    _lead_only(request)
    # El enlace recién generado se muestra una sola vez (queda en la sesión del admin, no en la base).
    links = {int(k): v for k, v in request.session.pop("signup_links", {}).items()}
    rows = onboarding.roster(links=links)
    return render(
        request,
        "team/people.html",
        {
            "areas": onboarding.groups_by_area(rows),
            "disciplines": Discipline.objects.all(),
            "can_name_leads": request.user.is_admin,
            "is_admin": request.user.is_admin,
            "fresh_links": [(r["person"], r["fresh_link"]) for r in rows if r["fresh_link"]],
            "invitation": onboarding.invitation_text(),
            "academy_url": onboarding.academy_url(),
            "step_labels": onboarding.STEP_LABELS,
            "total": len(rows),
        },
    )


@require_POST
def person_update(request, pk):
    _lead_only(request)
    person = get_object_or_404(Person, pk=pk)
    try:
        changes = onboarding.update_person(
            person,
            request.user,
            role=request.POST.get("role", ""),
            discipline_slugs=request.POST.getlist("disciplines"),
            job=request.POST.get("job", ""),
        )
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"{person.name}: {', '.join(changes)}." if changes else f"{person.name}: sin cambios.",
        )
    return redirect(f"/equipo/personas/#p{person.pk}")


@require_POST
def person_invited(request, pk):
    _lead_only(request)
    person = get_object_or_404(Person, pk=pk)
    onboarding.set_invited(person, request.user, request.POST.get("invited") == "1")
    return redirect(f"/equipo/personas/#p{person.pk}")


@require_POST
def person_signup_link(request, pk):
    _admin_only(request)
    person = get_object_or_404(Person, pk=pk)
    try:
        url = onboarding.create_signup_link(person, request.user)
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        links = request.session.get("signup_links", {})
        links[str(person.pk)] = url
        request.session["signup_links"] = links
        messages.success(
            request,
            f"Enlace de registro para {person.name}: cópialo ahora (se muestra una sola vez).",
        )
    return redirect(f"/equipo/personas/#p{person.pk}")


@require_http_methods(["GET", "POST"])
def people_add(request):
    _admin_only(request)
    text, report = "", None
    if request.method == "POST":
        upload = request.FILES.get("file")
        if upload is not None:
            if upload.size > onboarding.MAX_BYTES:
                messages.error(request, "El archivo es demasiado grande (máximo 200 KB).")
            else:
                text = upload.read().decode("utf-8-sig", errors="replace")
        else:
            text = request.POST.get("csv", "")
        if text:
            dry_run = request.POST.get("action") != "import"
            report = onboarding.import_team(text, by=request.user, dry_run=dry_run)
            if not dry_run and not report.fatal:
                messages.success(
                    request,
                    f"Listo: {report.count('created')} creadas, {report.count('updated')} actualizadas, "
                    f"{len(report.errors)} con errores.",
                )
        elif upload is None:
            messages.error(request, "Pega las filas o elige un archivo CSV.")
    return render(
        request,
        "team/people_add.html",
        {
            "text": text,
            "report": report,
            "template_csv": onboarding.TEMPLATE_CSV,
            "disciplines": Discipline.objects.all(),
            "can_name_leads": request.user.is_admin,
        },
    )
