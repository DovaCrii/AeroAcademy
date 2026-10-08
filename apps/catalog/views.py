from django.core.paginator import Paginator
from django.shortcuts import render

from . import services
from .models import Platform, Resource


def resources(request):
    """Catálogo de recursos con filtros por plataforma, tipo, gratuito y certificado."""
    params = request.GET
    kind = params.get("kind", "")
    qs = services.resource_queryset(
        platform=params.get("platform", ""),
        kind=kind if kind in Resource.Kind.values else "",
        free=params.get("free") == "1",
        cert=params.get("cert") == "1",
        q=params.get("q", "").strip()[:100],
    )
    page = Paginator(qs, 30).get_page(params.get("page"))
    query = params.copy()
    query.pop("page", None)
    return render(
        request,
        "catalog/resources.html",
        {
            "page": page,
            "platforms": Platform.objects.filter(resources__isnull=False).distinct(),
            "kinds": Resource.Kind.choices,
            "f": {
                "platform": params.get("platform", ""),
                "kind": kind,
                "free": params.get("free") == "1",
                "cert": params.get("cert") == "1",
                "q": params.get("q", "").strip()[:100],
            },
            "querystring": query.urlencode(),
        },
    )
