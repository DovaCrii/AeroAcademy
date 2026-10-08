from . import services


def teo(request):
    """El widget de Teo en la esquina solo necesita saber si está despierto."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or getattr(user, "status", "approved") != "approved":
        return {}
    return {"teo_awake": services.enabled()}
