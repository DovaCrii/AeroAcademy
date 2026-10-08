from django.http import Http404
from django.shortcuts import render

from . import services


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
