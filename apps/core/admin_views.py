"""Vistas del Centro de administración (D42). Finas: deciden quién entra y llaman a `admin_center`.

Quien no administra (miembro, puerta pública) recibe 404, igual que cualquier página que no existe: no se revela que
el Centro está ahí. El 405 de un método equivocado solo lo ve quien sí tiene acceso. Las acciones son POST con CSRF,
con redirección fija (nada de `next`) y mensaje en español.
"""

from functools import wraps

from django.contrib import messages
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.accounts import team_link
from apps.accounts.models import Person, PersonStatus
from apps.catalog.models import Discipline

from . import admin_center

# Dónde vuelve cada acción: las dos pantallas desde las que se pueden lanzar (lista blanca, sin `next` libre).
BACK = {"centro": "core:admin_center", "cuentas": "core:admin_accounts"}
SESSION_PERSONAL_LINKS = "admin_center_links"
SESSION_TEAM_LINK = "admin_center_team_link"


def admin_view(*, level=admin_center.LEAD, methods=("GET", "HEAD")):
    """Primero el acceso (404), después el método (405). `level`: «lead» deja entrar al responsable y al admin;
    «admin» solo al admin."""

    def decorator(view):
        @wraps(view)
        @never_cache
        def wrapper(request, *args, **kwargs):
            who = admin_center.access(request.user, request)
            if who is None or (level == admin_center.ADMIN and who != admin_center.ADMIN):
                raise Http404("No encontrado.")
            if request.method not in methods:
                return HttpResponseNotAllowed(methods)
            return view(request, who, *args, **kwargs)

        return wrapper

    return decorator


def _back(request, anchor: str = ""):
    """Vuelve a la pantalla de origen (`centro` o `cuentas`; por defecto, cuentas)."""
    target = reverse(BACK.get(request.POST.get("back", ""), "core:admin_accounts"))
    return redirect(f"{target}#{anchor}" if anchor else target)


@admin_view()
def center(request, who):
    is_admin = who == admin_center.ADMIN
    ctx = {
        "who": who,
        "is_admin": is_admin,
        "now": timezone.localtime(),
        "sections": admin_center.link_sections(who),
    }
    if is_admin:
        counts = admin_center.people_counts()
        link = team_link.active_link()
        pending = admin_center.pending_people()
        ctx.update(
            counts=counts,
            team_link=link,
            team_link_days=team_link.VALID_DAYS,
            team_link_default=team_link.DEFAULT_DAYS,
            # El enlace recién generado se muestra una sola vez: vive en la sesión hasta esta lectura.
            fresh_team_link=request.session.pop(SESSION_TEAM_LINK, ""),
            pending=pending,
            pending_more=max(counts["pending"] - len(pending), 0),
            filters=[
                {"key": key, "label": label, "n": counts[admin_center.STATE_COUNT[key]]}
                for key, label in admin_center.STATES.items()
                if key != "desactivada" or counts["deactivated"]
            ],
        )
        server = admin_center.server_status()
        ctx["server"] = server
        ctx["cards"] = admin_center.situation(who, counts=counts, link=link, server=server)
    else:
        ctx["cards"] = admin_center.situation(who)
    return render(request, "core/admin/center.html", ctx)


@admin_view()
def log(request, who):
    return render(
        request,
        "core/admin/log.html",
        {
            "who": who,
            **admin_center.log_page(
                action=request.GET.get("accion", ""), page=request.GET.get("pagina", 1)
            ),
        },
    )


# --- cuentas -------------------------------------------------------------------------------------------------------


@admin_view(level=admin_center.ADMIN)
def accounts(request, who):
    page = admin_center.accounts_page(
        request.user,
        state=request.GET.get("estado", ""),
        q=request.GET.get("q", ""),
        page=request.GET.get("pagina", 1),
    )
    # Los enlaces personales recién generados se muestran una sola vez (sesión de quien los generó, no la base).
    fresh = list(request.session.pop(SESSION_PERSONAL_LINKS, {}).values())
    return render(
        request,
        "core/admin/accounts.html",
        {
            **page,
            "who": who,
            "fresh_links": fresh,
            "disciplines": Discipline.objects.all()
            if any(r["can_approve"] for r in page["rows"])
            else [],
            "states": admin_center.STATES,
        },
    )


def _action_error(request, exc):
    messages.error(request, str(exc))


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_approve(request, who, pk):
    person = get_object_or_404(Person, pk=pk, status=PersonStatus.PENDING)
    try:
        admin_center.approve_pending(
            person,
            request.user,
            role=request.POST.get("role", "member"),
            discipline_slugs=request.POST.getlist("disciplines"),
            character_class=request.POST.get("character_class", ""),
        )
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        messages.success(request, f"{person.name} fue aprobada.")
    return _back(request, f"p{person.pk}")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_reject(request, who, pk):
    person = get_object_or_404(Person, pk=pk, status=PersonStatus.PENDING)
    try:
        admin_center.reject_pending(person, request.user)
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        messages.success(request, f"Se rechazó el acceso de {person.name}.")
    return _back(request, f"p{person.pk}")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_role(request, who, pk):
    person = get_object_or_404(Person, pk=pk)
    try:
        changed = admin_center.change_role(person, request.user, request.POST.get("role", ""))
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        messages.success(
            request,
            f"{person.name}: rol cambiado." if changed else f"{person.name}: el rol ya era ese.",
        )
    return _back(request, f"p{person.pk}")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_suspend(request, who, pk):
    person = get_object_or_404(Person, pk=pk)
    try:
        done = admin_center.suspend_account(person, request.user)
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        messages.success(
            request,
            f"{person.name} quedó suspendida: no puede entrar, sus datos se conservan."
            if done
            else f"{person.name} ya estaba suspendida.",
        )
    return _back(request, f"p{person.pk}")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_reactivate(request, who, pk):
    person = get_object_or_404(Person, pk=pk)
    try:
        done = admin_center.reactivate_account(person, request.user)
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        messages.success(
            request,
            f"{person.name} volvió a tener acceso."
            if done
            else f"{person.name} no estaba suspendida.",
        )
    return _back(request, f"p{person.pk}")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def account_link(request, who, pk):
    person = get_object_or_404(Person, pk=pk)
    try:
        url = admin_center.personal_link(person, request.user)
    except (PermissionError, ValueError) as exc:
        _action_error(request, exc)
    else:
        links = request.session.get(SESSION_PERSONAL_LINKS, {})
        links[str(person.pk)] = {"name": person.name, "url": url}
        request.session[SESSION_PERSONAL_LINKS] = links
        messages.success(
            request,
            f"Enlace de registro para {person.name}: cópialo ahora (se muestra una sola vez).",
        )
    return _back(request, f"p{person.pk}")


# --- enlace del equipo ------------------------------------------------------------------------------------------


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def team_link_create(request, who):
    try:
        days = int(request.POST.get("days") or team_link.DEFAULT_DAYS)
        url = team_link.generate(request.user, days)
    except ValueError:
        messages.error(request, "La vigencia debe ser de 7, 14 o 30 días.")
    else:
        request.session[SESSION_TEAM_LINK] = url
        messages.success(
            request,
            "Enlace del equipo generado: cópialo ahora (se muestra una sola vez). El anterior dejó de servir.",
        )
    return redirect(reverse("core:admin_center") + "#enlace")


@admin_view(level=admin_center.ADMIN, methods=("POST",))
def team_link_revoke(request, who):
    if team_link.revoke(request.user):
        messages.success(request, "Enlace del equipo revocado.")
    else:
        messages.info(request, "No había un enlace vigente.")
    return redirect(reverse("core:admin_center") + "#enlace")
