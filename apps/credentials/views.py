from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Platform, Skill
from apps.paths import services as path_services
from apps.paths.models import LearningPath

from . import files, services
from .forms import CredentialForm, RegisterCourseForm
from .models import Credential


def _visible_or_404(request, pk):
    cred = get_object_or_404(
        Credential.objects.select_related("owner", "resource", "path", "platform"), pk=pk
    )
    if not services.can_view(request.user, cred):
        raise Http404
    return cred


def mine(request):
    """Mis credenciales."""
    creds = list(services.for_owner(request.user))
    return render(
        request,
        "credentials/mine.html",
        {
            "credentials": creds,
            "counts": {
                "verified": sum(c.status == Credential.Status.VERIFIED for c in creds),
                "pending": sum(c.status == Credential.Status.PENDING for c in creds),
                "rejected": sum(c.status == Credential.Status.REJECTED for c in creds),
                "expiring": sum(c.expires_soon or c.is_expired for c in creds),
            },
        },
    )


@require_http_methods(["GET", "POST"])
def create(request):
    form = CredentialForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        cred = services.create_credential(
            request.user, form.data_for_service(), form.cleaned_data["file"]
        )
        messages.success(request, "Credencial enviada. Un responsable la revisará.")
        return redirect("credentials:detail", pk=cred.pk)
    return render(
        request,
        "credentials/form.html",
        {"form": form, "title": "Nueva credencial", "editing": False},
    )


def detail(request, pk):
    cred = _visible_or_404(request, pk)
    return render(
        request,
        "credentials/detail.html",
        {
            "cred": cred,
            "can_download": services.can_download(request.user, cred),
            "can_edit": services.can_edit(request.user, cred),
            "can_review": services.can_review(request.user),
            "version": services.version_of(cred),
            "is_free_course": not cred.resource_id and bool(cred.course_name_free),
        },
    )


@require_http_methods(["GET", "POST"])
def edit(request, pk):
    cred = _visible_or_404(request, pk)
    if not services.can_edit(request.user, cred):
        raise PermissionDenied
    form = CredentialForm(request.POST or None, request.FILES or None, instance=cred)
    if request.method == "POST" and form.is_valid():
        back = services.update_credential(
            cred, form.data_for_service(), form.cleaned_data.get("file")
        )
        messages.success(
            request,
            "Cambios guardados. La credencial volvió a revisión." if back else "Cambios guardados.",
        )
        return redirect("credentials:detail", pk=cred.pk)
    return render(
        request,
        "credentials/form.html",
        {"form": form, "title": "Editar credencial", "editing": True, "cred": cred},
    )


def download(request, pk):
    """Entrega el archivo solo a la persona dueña y a los responsables; nunca como estático (D4)."""
    cred = _visible_or_404(request, pk)
    if not services.can_download(request.user, cred):
        raise PermissionDenied
    ext = cred.file_kind or "bin"
    try:
        handle = cred.file.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404("El archivo ya no está disponible.") from None
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=f"credencial-{cred.pk}.{ext}",
        content_type=files.CONTENT_TYPES.get(ext, "application/octet-stream"),
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def delete(request, pk):
    cred = _visible_or_404(request, pk)
    if not services.can_edit(request.user, cred):
        raise PermissionDenied
    services.delete_credential(cred)
    messages.success(request, "Credencial eliminada.")
    return redirect("credentials:mine")


def team(request):
    """Credenciales verificadas del equipo (solo el listado, sin abrir el archivo)."""
    p = request.GET
    qs = services.team_visible()
    if p.get("tipo") in Credential.Kind.values:
        qs = qs.filter(kind=p["tipo"])
    if p.get("plataforma"):
        qs = qs.filter(platform__slug=p["plataforma"])
    if p.get("habilidad"):
        qs = qs.filter(skills__slug=p["habilidad"])
    if p.get("q"):
        qs = qs.filter(Q(title__icontains=p["q"][:100]) | Q(issuer__icontains=p["q"][:100]))
    creds = list(qs.distinct().prefetch_related("skills"))
    if p.get("vencen") == "1":
        creds = [c for c in creds if c.expires_soon or c.is_expired]
    return render(
        request,
        "credentials/team.html",
        {
            "credentials": creds,
            "platforms": Platform.objects.filter(credentials__isnull=False).distinct(),
            "skills": Skill.objects.filter(credentials__isnull=False).distinct(),
            "kinds": Credential.Kind.choices,
            "f": {k: p.get(k, "") for k in ("tipo", "plataforma", "habilidad", "q", "vencen")},
        },
    )


def review_queue(request):
    if not services.can_review(request.user):
        raise PermissionDenied
    return render(request, "credentials/review.html", {"credentials": services.review_queue()})


@require_POST
def review(request, pk):
    if not services.can_review(request.user):
        raise PermissionDenied
    cred = get_object_or_404(Credential, pk=pk)
    action = request.POST.get("action")
    comment = request.POST.get("comment", "")[:1000]
    version = request.POST.get("version") or None
    back = _safe_next(request)
    try:
        if action == "verify":
            services.verify(cred, request.user, comment, version=version)
            messages.success(request, f"«{cred.display_title}» quedó verificada.")
        elif action == "reject":
            services.reject(cred, request.user, comment, version=version)
            messages.success(request, f"«{cred.display_title}» fue rechazada.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(back)


def _safe_next(request):
    """Solo se vuelve a una ruta de este mismo sitio (nunca a un `next` externo)."""
    target = request.POST.get("next", "")
    allowed = url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return (
        target
        if target and allowed and target.startswith("/")
        else reverse("credentials:review_queue")
    )


@require_POST
def promote(request, pk):
    if not services.can_review(request.user):
        raise PermissionDenied
    cred = get_object_or_404(Credential, pk=pk)
    try:
        resource = services.promote_free_course(cred, request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"«{resource.title}» ya forma parte de la ruta.")
    return redirect("credentials:detail", pk=cred.pk)


@require_http_methods(["GET", "POST"])
def register_course(request, slug):
    """Registrar un curso de una ruta externa (ej.: Bentley Learn) con su certificado."""
    path = path_services.visible_paths(request.user).filter(slug=slug).first()
    if path is None or path.kind != LearningPath.Kind.EXTERNAL_TRACK:
        raise Http404
    initial = {"course": request.GET.get("curso", "")}
    form = RegisterCourseForm(
        request.POST or None, request.FILES or None, path=path, owner=request.user, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        cred = services.create_credential(
            request.user, form.data_for_service(), form.cleaned_data["file"]
        )
        messages.success(request, "Curso registrado. Un responsable verificará el certificado.")
        return redirect("credentials:detail", pk=cred.pk)
    return render(request, "credentials/register.html", {"form": form, "path": path})
