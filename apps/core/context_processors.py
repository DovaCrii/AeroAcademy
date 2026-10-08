from django.conf import settings


def brand(request):
    return {
        "BRAND_PLATFORM": settings.BRAND_PLATFORM,
        "BRAND_ACADEMY": settings.BRAND_ACADEMY,
    }
