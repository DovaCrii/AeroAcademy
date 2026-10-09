from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.models import Person, PersonStatus
from apps.paths.models import LearningPath

from . import services


def _owner_or_404(request):
    """Cada quien ve el suyo; quien lidera puede ver el de otra persona con `?persona=<pk>`. Lo demás es 404."""
    raw = request.GET.get("persona")
    if raw in (None, ""):
        return request.user
    try:
        pk = int(raw)
    except ValueError:
        raise Http404 from None
    if pk == request.user.pk:
        return request.user
    if not request.user.is_lead:
        raise Http404  # no se revela que existe
    owner = Person.objects.filter(pk=pk, status=PersonStatus.APPROVED, is_active=True).first()
    if owner is None:
        raise Http404
    return owner


@require_GET
def detail(request, slug):
    owner = _owner_or_404(request)
    path = LearningPath.objects.filter(slug=slug).select_related("platform").first()
    if path is None or not services.has_diploma(path):
        raise Http404  # rutas de fabricantes: su certificado es el que entrega el fabricante
    ctx = services.diploma_context(owner, path)
    if ctx is None:
        return render(
            request,
            "diplomas/pending.html",
            {"path": path, "owner": owner, "own": owner.pk == request.user.pk},
            status=404,
        )
    ctx.update(
        back=f"/rutas/{path.slug}/",
        own=owner.pk == request.user.pk,
        page_title=f"Diploma · {path.title}",
    )
    return render(request, "diplomas/diploma.html", ctx)
