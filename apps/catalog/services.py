from django.db.models import Q

from .models import Resource


def resource_queryset(*, platform="", kind="", free=False, cert=False, q="", product=""):
    qs = Resource.objects.select_related("platform").prefetch_related("skills", "products")
    if platform:
        qs = qs.filter(platform__slug=platform)
    if kind:
        qs = qs.filter(kind=kind)
    if free:
        qs = qs.filter(is_free=True)
    if cert:
        qs = qs.filter(grants_completion_certificate=True)
    if product:
        qs = qs.filter(products__slug=product)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return qs.distinct()
