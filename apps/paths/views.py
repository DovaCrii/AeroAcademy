from django.http import Http404
from django.shortcuts import render

from apps.progress import services as progress_services
from apps.progress.views import world_template

from . import services
from .models import LearningPath


def index(request):
    """Rutas: pestañas por vendor → productos → campañas, con filtros por disciplina y habilidad."""
    p = request.GET
    ctx = services.path_listing(
        request.user,
        vendor=p.get("vendor", ""),
        product=p.get("product", ""),
        discipline=p.get("discipline", ""),
        skill=p.get("skill", ""),
    )
    ctx["f"] = {k: p.get(k, "") for k in ("product", "discipline", "skill")}
    return render(request, "paths/index.html", ctx)


def detail(request, slug):
    path = services.visible_paths(request.user).filter(slug=slug).first()
    if path is None:
        raise Http404

    # Las rutas estructuradas con mundo propio se muestran con su diseño (docs/MUNDOS.md).
    if path.kind == LearningPath.Kind.STRUCTURED and path.world:
        full = world_template(path.world, "path.html")
        if full:
            ctx = progress_services.world_context(request.user, path, request.GET.get("nivel"))
            template = (
                world_template(path.world, "_app.html")
                if request.headers.get("X-Partial")
                else full
            )
            return render(request, template, ctx)

    return render(
        request,
        "paths/detail.html",
        {
            "path": path,
            "chapters": services.path_detail(path),
            "products": path.products.all(),
            "disciplines": path.disciplines.all(),
        },
    )
