import re

from apps.paths.models import LearningPath

from . import services

_PATH_URL = re.compile(r"^/(?:rutas|equipo/kit)/([\w-]+)/")
WORLD_SPRITES = {"architecture", "civil", "survey", "mechanical", "aero"}
# Fuera de una ruta, Nala se viste como la carrera de la persona (apps/gamification/avatar/careers.py).
CAREER_WORLD = {
    "arquitectura": "architecture",
    "civil": "civil",
    "topografia": "survey",
    "mecanica": "mechanical",
    "captura": "aero",
}
GREETING = "¡Hola, soy Nala! 🐾 Te acompaño en la academia: pregúntame o usa un atajo."
GREETING_ASLEEP = "¡Hola, soy Nala! 🐾 Ahora estoy durmiendo, pero los atajos funcionan igual."


def _career_world(user):
    from apps.gamification.avatar.careers import CAREERS

    career = CAREERS.get(getattr(user, "character_class", "") or "")
    return CAREER_WORLD.get(career["discipline"]) if career else None


def _sprite(request, awake):
    """Atuendo de Nala: el del mundo de la ruta que se mira (o la sección DGAC); si no, el de la carrera de la
    persona; si duerme, durmiendo."""
    if not awake:
        return "teo-sleep.svg"
    if request.path.startswith("/dgac/"):
        return "teo-aero.svg"
    match = _PATH_URL.match(request.path)
    if match:
        world = (
            LearningPath.objects.filter(slug=match.group(1)).values_list("world", flat=True).first()
        )
        if world in WORLD_SPRITES:
            return f"teo-{world}.svg"
    world = _career_world(request.user)
    return f"teo-{world}.svg" if world else "teo-idle.svg"


def teo(request):
    """El widget de Nala en la esquina: si está despierta, cómo va vestida y cómo saluda."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or getattr(user, "status", "approved") != "approved":
        return {}
    awake = services.enabled()
    from .quick import SHORTCUTS

    return {
        "teo_awake": awake,
        "teo_sprite": _sprite(request, awake),
        "teo_shortcuts": SHORTCUTS,
        "nala_greeting": GREETING if awake else GREETING_ASLEEP,
    }
