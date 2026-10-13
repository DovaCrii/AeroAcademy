from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalog import guides
from apps.core import private_files
from apps.progress import external as progress_external
from apps.progress import services as progress_services
from apps.progress.views import resolve_world, world_template

from . import metro, services
from .models import LearningPath


@require_GET
def course_photo(request, slug, name):
    """Foto privada de un curso: solo si la ruta es visible para la persona (lo oculto o en borrador es 404)."""
    if services.visible_paths(request.user).filter(slug=slug).first() is None:
        raise Http404
    path = guides.photo_path(slug, name)
    if path is None:
        raise Http404
    return private_files.file_response(path)


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


@require_GET
def metro_map(request):
    """Mapa de metro: líneas = disciplinas, estaciones = rutas, transbordos = rutas compartidas."""
    return render(request, "paths/map.html", {"metro": metro.build_map(request.user)})


def detail(request, slug):
    path = services.visible_paths(request.user).filter(slug=slug).first()
    if path is None:
        raise Http404

    # Las rutas con mundo propio se muestran con su diseño (docs/MUNDOS.md); si no, el de respaldo de su tipo.
    world = resolve_world(path)
    if world:
        full = world_template(world, "path.html")
        if full:
            if path.kind == LearningPath.Kind.EXTERNAL_TRACK:
                ctx = progress_external.external_context(
                    request.user, path, request.GET.get("nivel")
                )
            else:
                ctx = progress_services.world_context(
                    request.user, path, request.GET.get("nivel"), request.GET.get("paso")
                )
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
