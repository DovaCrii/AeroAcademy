"""Navegación principal de la cabecera: UN solo lugar define qué va en la barra y qué va en «Más».

Para mover una sección (por ejemplo Certificados) basta con cambiar de tupla; la plantilla, el menú
hamburguesa y las pruebas leen estas listas. Producto: docs/DECISIONES.md (Certificados en «Más»).
"""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    app: str  # app_name que la marca como activa
    only: tuple[str, ...] = ()  # si no está vacío, solo estas vistas la marcan
    exclude: tuple[str, ...] = ()
    lead_only: bool = False


# Cinco principales: nunca se cortan ni se envuelven (ver base.css).
MAIN_NAV = (
    NavItem("Inicio", "core:home", "core", only=("home",)),
    NavItem("Rutas", "paths:index", "paths"),
    NavItem("Catálogo", "catalog:resources", "catalog"),
    NavItem("Foro", "community:forum", "community", exclude=("moderation",)),
    NavItem("Equipo", "team:board", "team"),
)

# Secundarias: viven en el menú «Más» (y en la hamburguesa bajo 1024 px).
MORE_NAV = (
    NavItem("Certificados", "credentials:mine", "credentials"),
    NavItem("Documentos", "library:index", "library"),
    NavItem("Conocimiento", "knowledge:index", "knowledge"),
    NavItem("Gremio", "gamification:directory", "gamification", only=("directory",)),
    NavItem("DGAC", "dgac:home", "dgac"),
    NavItem("Ayuda", "assistant:help_index", "assistant", only=("help_index", "help")),
    NavItem(
        "Moderación", "community:moderation", "community", only=("moderation",), lead_only=True
    ),
)


def _current(item: NavItem, app: str, name: str) -> bool:
    if item.app != app:
        return False
    if item.only:
        return name in item.only
    return name not in item.exclude


def _build(items, app, name, is_lead):
    return [
        {"label": i.label, "url": reverse(i.url_name), "current": _current(i, app, name)}
        for i in items
        if is_lead or not i.lead_only
    ]


def navigation(request):
    match = getattr(request, "resolver_match", None)
    app = (match.app_name if match else "") or ""
    name = (match.url_name if match else "") or ""
    is_lead = bool(getattr(getattr(request, "user", None), "is_lead", False))
    more = _build(MORE_NAV, app, name, is_lead)
    return {
        "nav_main": _build(MAIN_NAV, app, name, is_lead),
        "nav_more": more,
        "nav_more_on": any(i["current"] for i in more),
    }
