from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.catalog.models import Discipline

from . import files, services
from .models import Document, DocumentVersion

PAGE_SIZE = 20


def _doc_or_404(request, pk):
    doc = get_object_or_404(Document.objects.select_related("owner"), pk=pk)
    if not services.can_view(request.user, doc):
        raise Http404  # no se revela que existe
    return doc


def _form_data(post):
    return {
        "title": post.get("title", ""),
        "doc_type": post.get("doc_type", ""),
        "description": post.get("description", ""),
        "tags": post.get("tags", ""),
        "disciplines": Discipline.objects.filter(slug__in=post.getlist("disciplines")),
        "restricted": post.get("restricted") == "on",
    }


def _form_context(**extra):
    return {
        "types": Document.Type.choices,
        "disciplines": Discipline.objects.all(),
        "max_mb": files.MAX_BYTES // (1024 * 1024),
        "extensions": ", ".join(sorted(files.ALLOWED_EXTENSIONS)),
        **extra,
    }


@require_GET
def index(request):
    p = request.GET
    discipline = Discipline.objects.filter(slug=p.get("disciplina", "")).first()
    page = Paginator(
        services.listing(
            request.user,
            q=p.get("q", "").strip()[:100],
            doc_type=p.get("tipo", ""),
            discipline=discipline,
            tag=p.get("etiqueta", "").strip().lower()[:30],
        ),
        PAGE_SIZE,
    ).get_page(p.get("pagina"))
    query = p.copy()
    query.pop("pagina", None)
    return render(
        request,
        "library/index.html",
        {
            "page": page,
            "types": Document.Type.choices,
            "disciplines": Discipline.objects.all(),
            "tags": services.all_tags(request.user),
            "f": {k: p.get(k, "") for k in ("q", "tipo", "disciplina", "etiqueta")},
            "qs": query.urlencode(),
        },
    )


@require_http_methods(["GET", "POST"])
def new(request):
    if request.method == "POST":
        upload = request.FILES.get("file")
        try:
            if upload is None:
                raise ValueError("Elige el archivo.")
            doc = services.create_document(
                request.user,
                upload=upload,
                label=request.POST.get("version_label", ""),
                notes=request.POST.get("notes", ""),
                **_form_data(request.POST),
            )
        except (ValueError, ValidationError) as exc:
            messages.error(
                request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            messages.success(request, "Documento publicado.")
            return redirect("library:detail", pk=doc.pk)
    return render(request, "library/form.html", _form_context(v=request.POST, editing=False))


@require_GET
def detail(request, pk):
    doc = _doc_or_404(request, pk)
    return render(
        request,
        "library/detail.html",
        {
            "doc": doc,
            "versions": list(doc.versions.select_related("uploaded_by")),
            "disciplines": doc.disciplines.all(),
            "can_edit": services.can_edit(request.user, doc),
            "max_mb": files.MAX_BYTES // (1024 * 1024),
        },
    )


@require_http_methods(["GET", "POST"])
def edit(request, pk):
    doc = _doc_or_404(request, pk)
    if not services.can_edit(request.user, doc):
        raise Http404
    if request.method == "POST":
        try:
            services.update_document(doc, request.user, **_form_data(request.POST))
        except (ValueError, PermissionError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Documento actualizado.")
            return redirect("library:detail", pk=doc.pk)
    initial = {
        "title": doc.title,
        "doc_type": doc.doc_type,
        "description": doc.description,
        "tags": ", ".join(doc.tags),
        "restricted": "on" if doc.is_restricted else "",
    }
    return render(
        request,
        "library/form.html",
        _form_context(
            v=request.POST or initial,
            editing=True,
            doc=doc,
            chosen=[d.slug for d in doc.disciplines.all()],
        ),
    )


@require_POST
def upload(request, pk):
    doc = _doc_or_404(request, pk)
    file = request.FILES.get("file")
    try:
        if file is None:
            raise ValueError("Elige el archivo.")
        services.upload_version(
            doc,
            request.user,
            file,
            label=request.POST.get("version_label", ""),
            notes=request.POST.get("notes", ""),
        )
    except (ValueError, ValidationError, PermissionError) as exc:
        messages.error(
            request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        )
    else:
        messages.success(request, "Versión nueva subida: ahora es la vigente.")
    return redirect("library:detail", pk=doc.pk)


@require_POST
def make_current(request, pk, version_pk):
    doc = _doc_or_404(request, pk)
    version = get_object_or_404(DocumentVersion, pk=version_pk, document=doc)
    try:
        services.make_current(version, request.user)
        messages.success(request, f"«{version.version_label}» es ahora la versión vigente.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect("library:detail", pk=doc.pk)


@require_POST
def delete(request, pk):
    doc = _doc_or_404(request, pk)
    try:
        services.delete_document(doc, request.user)
    except PermissionError as exc:
        messages.error(request, str(exc))
        return redirect("library:detail", pk=doc.pk)
    messages.success(request, "Documento eliminado.")
    return redirect("library:index")


@require_GET
def download(request, pk, version_pk=None):
    """Entrega el archivo por una vista con permiso: nunca por una URL pública."""
    doc = _doc_or_404(request, pk)
    versions = doc.versions.all()
    version = (
        get_object_or_404(versions, pk=version_pk)
        if version_pk
        else versions.filter(is_current=True).first()
    )
    if version is None:
        raise Http404
    try:
        handle = version.file.open("rb")
    except (OSError, ValueError):
        raise Http404 from None
    name = f"{slugify(doc.title) or 'documento'}-{slugify(version.version_label) or 'v'}.{version.file_ext}"
    response = FileResponse(
        handle, as_attachment=True, filename=name, content_type=files.CONTENT_TYPE
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
