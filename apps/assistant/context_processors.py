import re

from apps.paths.models import LearningPath

from . import services

_PATH_URL = re.compile(r"^/(?:rutas|equipo/kit)/([\w-]+)/")
WORLD_SPRITES = {"architecture", "civil", "survey", "mechanical", "aero"}


def _sprite(request, awake):
    """Atuendo de Teo: el del mundo de la ruta que se mira; si duerme, durmiendo."""
    if not awake:
        return "teo-sleep.svg"
    match = _PATH_URL.match(request.path)
    if match:
        world = (
            LearningPath.objects.filter(slug=match.group(1)).values_list("world", flat=True).first()
        )
        if world in WORLD_SPRITES:
            return f"teo-{world}.svg"
    return "teo-idle.svg"


def teo(request):
    """El widget de Teo en la esquina solo necesita saber si está despierto y cómo va vestido."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or getattr(user, "status", "approved") != "approved":
        return {}
    awake = services.enabled()
    return {"teo_awake": awake, "teo_sprite": _sprite(request, awake)}
