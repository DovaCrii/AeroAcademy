from django.http import Http404
from django.shortcuts import render

from apps.progress import external as progress_external
from apps.progress import services as progress_services
from apps.progress.views import world_template

from . import services
from .models import LearningPath

# Qué tipos de ruta sabe dibujar cada mundo, y a cuál se recurre si el suyo no puede.
WORLD_KINDS = {
    "architecture": {LearningPath.Kind.STRUCTURED},
    "civil": {LearningPath.Kind.EXTERNAL_TRACK},
    "aero": {LearningPath.Kind.STRUCTURED},
}
KIND_FALLBACK_WORLD = {
    LearningPath.Kind.STRUCTURED: "architecture",
    LearningPath.Kind.EXTERNAL_TRACK: "civil",
}


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

    # Las rutas con mundo propio se muestran con su diseño (docs/MUNDOS.md). Si el mundo no sabe mostrar ese tipo de
    # ruta (p. ej. Civil 3D, estructurada, en el mundo civil hecho para Bentley), se usa uno que sí: nunca una ruta vacía.
    # Lo mismo si el mundo todavía no tiene diseño (p. ej. «survey» en Topografía 101): mejor el de su tipo con guías e
    # imágenes que la página genérica.
    world = path.world
    if world and (
        path.kind not in WORLD_KINDS.get(world, {path.kind})
        or not world_template(world, "path.html")
    ):
        world = KIND_FALLBACK_WORLD.get(path.kind, "")
    if world:
        full = world_template(world, "path.html")
        if full:
            builder = (
                progress_external.external_context
                if path.kind == LearningPath.Kind.EXTERNAL_TRACK
                else progress_services.world_context
            )
            ctx = builder(request.user, path, request.GET.get("nivel"))
            template = (
                world_template(world, "_app.html") if request.headers.get("X-Partial") else full
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
