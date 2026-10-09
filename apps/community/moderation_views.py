from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from apps.accounts import services as accounts
from apps.accounts.models import CharacterClass, Person, PersonStatus
from apps.catalog.models import Discipline
from apps.credentials import services as credential_services
from apps.notifications import services as notifications
from apps.notifications.models import Announcement

from . import moderation, opinions
from .models import Category, ModerationLog, Note, Post, Report, Thread

LOG_LIMIT = 50


def _lead_only(request):
    if not request.user.is_lead:
        raise PermissionDenied


def _run(request, fn, *args, ok="", **kwargs):
    """Ejecuta una acción de moderación y la informa; los errores de regla se muestran, no se propagan."""
    try:
        fn(*args, **kwargs)
    except PermissionError as exc:
        messages.error(request, str(exc))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        if ok:
            messages.success(request, ok)
        return True
    return False


@require_GET
def dashboard(request):
    _lead_only(request)
    reports = []
    for r in moderation.open_reports()[:50].select_related("reporter"):
        target = moderation.target_of(r)
        text = (getattr(target, "body", None) or getattr(target, "text", "")) if target else ""
        reports.append({"report": r, "target": target, "text": text})
    return render(
        request,
        "community/moderation.html",
        {
            "pending": Person.objects.filter(status=PersonStatus.PENDING).order_by("created_at"),
            "to_review": credential_services.review_queue().count(),
            "reports": reports,
            "announcements": notifications.active_announcements(),
            "log": ModerationLog.objects.select_related("actor")[:LOG_LIMIT],
            "disciplines": Discipline.objects.all(),
            "classes": CharacterClass.choices,
            "can_name_leads": request.user.is_admin,
            "today": date.today().isoformat(),
        },
    )


@require_POST
def approve_person(request, pk):
    _lead_only(request)
    person = get_object_or_404(Person, pk=pk, status=PersonStatus.PENDING)
    role = request.POST.get("role", "member")
    if role not in ("member", "lead") or (role == "lead" and not request.user.is_admin):
        role = "member"
    disciplines = Discipline.objects.filter(slug__in=request.POST.getlist("disciplines"))
    cls = request.POST.get("character_class", "")
    accounts.approve(person, request.user)
    accounts.set_role(person, role)
    person.disciplines.set(disciplines)
    if cls in CharacterClass.values:
        person.character_class = cls
        person.save(update_fields=["character_class", "updated_at"])
    moderation.log(request.user, "approve_person", person, person.name, role)
    messages.success(request, f"{person.name} fue aprobada.")
    return redirect("community:moderation")


@require_POST
def reject_person(request, pk):
    _lead_only(request)
    person = get_object_or_404(Person, pk=pk, status=PersonStatus.PENDING)
    accounts.suspend(person)
    moderation.log(request.user, "reject_person", person, person.name)
    messages.success(request, f"Se rechazó el acceso de {person.name}.")
    return redirect("community:moderation")


@require_POST
def resolve_report(request, pk):
    _lead_only(request)
    report = get_object_or_404(Report, pk=pk)
    hide = request.POST.get("action") == "hide"
    _run(
        request,
        moderation.resolve_report,
        report,
        request.user,
        hide=hide,
        reason=request.POST.get("reason", ""),
        ok="Reporte resuelto.",
    )
    return redirect("community:moderation")


@require_POST
def new_announcement(request):
    _lead_only(request)
    try:
        expires = date.fromisoformat(request.POST.get("expires_on", ""))
    except ValueError:
        messages.error(request, "Indica una fecha de vencimiento válida.")
        return redirect("community:moderation")
    _run(
        request,
        notifications.publish_announcement,
        request.user,
        request.POST.get("title", ""),
        request.POST.get("body", ""),
        expires,
        ok="Anuncio publicado y avisado a todo el equipo.",
    )
    return redirect("community:moderation")


@require_POST
def remove_announcement(request, pk):
    _lead_only(request)
    ann = get_object_or_404(Announcement, pk=pk)
    _run(request, notifications.delete_announcement, ann, request.user, ok="Anuncio retirado.")
    return redirect("community:moderation")


# --- acciones sobre contenido ------------------------------------------------------------------------------------


@require_POST
def moderate_thread(request, pk):
    _lead_only(request)
    thread = get_object_or_404(Thread, pk=pk)
    action, p = request.POST.get("action", ""), request.POST
    if action in ("pin", "unpin"):
        _run(request, moderation.pin, thread, request.user, action == "pin", ok="Hecho.")
    elif action in ("hide", "unhide"):
        _run(
            request,
            moderation.set_hidden,
            thread,
            request.user,
            action == "hide",
            p.get("reason", ""),
            ok="Hecho.",
        )
    elif action == "rename":
        _run(
            request,
            moderation.rename_thread,
            thread,
            request.user,
            p.get("title", ""),
            ok="Título cambiado.",
        )
    elif action == "move":
        category = Category.objects.filter(slug=p.get("category", "")).first()
        if category is None:
            messages.error(request, "Elige una categoría.")
        else:
            disciplines = Discipline.objects.filter(slug__in=p.getlist("disciplines"))
            _run(
                request,
                moderation.move_thread,
                thread,
                request.user,
                category,
                disciplines,
                ok="Hilo movido.",
            )
    else:
        messages.error(request, "Acción desconocida.")
    return redirect("community:thread", pk=pk)


def _moderate_item(request, model, pk, back):
    _lead_only(request)
    obj = get_object_or_404(model, pk=pk)
    hide = request.POST.get("action") == "hide"
    _run(
        request,
        moderation.set_hidden,
        obj,
        request.user,
        hide,
        request.POST.get("reason", ""),
        ok="Hecho.",
    )
    return back(obj)


@require_POST
def moderate_post(request, pk):
    return _moderate_item(request, Post, pk, lambda o: redirect("community:thread", pk=o.thread_id))


@require_POST
def moderate_note(request, pk):
    return _moderate_item(
        request, Note, pk, lambda o: redirect("community:path_notes", slug=o.path.slug)
    )


@require_POST
def report(request, kind, pk):
    back = request.POST.get("next", "")
    ok = back.startswith("/") and url_has_allowed_host_and_scheme(back, {request.get_host()})
    _run(
        request,
        moderation.report_content,
        request.user,
        kind,
        pk,
        request.POST.get("reason", ""),
        ok="Gracias: un responsable revisará el reporte.",
    )
    return redirect(back if ok else "community:forum")


@require_POST
def clear_opinions(request, pk):
    """Limpia reacciones (y votos de la encuesta) de un hilo oculto; con `post` limpia las de un mensaje oculto."""
    _lead_only(request)
    post_pk = request.POST.get("post", "")
    if post_pk:
        post = get_object_or_404(Post, pk=post_pk, thread_id=pk)
        _run(request, opinions.clear_reactions, post, request.user, ok="Reacciones limpiadas.")
    else:
        thread = get_object_or_404(Thread, pk=pk)
        _run(request, opinions.clear_reactions, thread, request.user, ok="Reacciones limpiadas.")
        if request.POST.get("votes"):
            _run(request, opinions.clear_votes, thread, request.user, ok="Votos limpiados.")
    return redirect("community:thread", pk=pk)
