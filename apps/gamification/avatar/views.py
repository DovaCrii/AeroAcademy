"""Vistas del avatar: recortes de la grilla, siempre en celdas enteras (docs/AVATAR_REDISENO.md § d.1).

Cada vista es `(x, y, ancho, alto)` en celdas de la grilla. Un tamaño en píxeles solo es válido si su ancho es un múltiplo
entero del ancho de la vista: así cada celda mide un número entero de píxeles y no hay franjas desiguales.

`SCALE` multiplica la grilla: con 1 es el 32×32 de siempre y con 2 salen las mismas cajas en la figura HD de 64×64
(docs/AVATAR_RESOLUCION.md), sin números sueltos. La vista `stage` es el escenario de 80×80 con esa figura adentro
y sus tamaños válidos son 80, 160, 240…
"""

from .art import GRID

SCALE = 1  # 1 = grilla de 32; las vistas HD multiplican las mismas cajas por 2
STAGE = 80  # escenario HD: 80×80 celdas con la figura de 64×64 adentro (ver `hd/`)

# Recortes de la figura (grilla de 32). Los de zona sirven de miniatura de una pieza: ojos, boca, torso, piernas.
VIEWS = {
    "full": (0, 0, GRID, GRID),
    "bust": (4, 2, 24, 24),
    "top": (4, 0, 24, 16),  # pelo y gorro: la parte de arriba de la cabeza
    "head": (8, 3, 16, 16),
    "zone:eyes": (10, 8, 12, 6),  # cejas y ojos
    "zone:glasses": (6, 8, 20, 6),  # lentes
    "zone:mouth": (10, 12, 12, 6),  # nariz y boca
    "zone:torso": (4, 19, 24, 9),  # ropa
    "zone:neck": (8, 18, 16, 8),  # cuello
    "zone:pin": (14, 18, 12, 8),  # pin de solapa
    "zone:legs": (4, 26, 24, 6),  # parte de abajo
    "zone:bg": (0, 0, 16, 16),  # muestra de un fondo, sin figura
}


def box(view, scale=SCALE):
    """Caja `(x, y, ancho, alto)` de una vista con nombre o de un rectángulo `(x, y, ancho, alto)` en celdas."""
    if view == "stage":
        return 0, 0, STAGE, STAGE
    if isinstance(view, tuple):
        x, y, w, h = view
        if not (0 <= x and 0 <= y and w > 0 and h > 0 and x + w <= GRID and y + h <= GRID):
            raise ValueError(f"recorte fuera de la grilla: {view}")
    else:
        x, y, w, h = VIEWS.get(view, VIEWS["full"])
    return x * scale, y * scale, w * scale, h * scale


def valid_width(view, width, scale=SCALE):
    """`True` si el ancho en píxeles es un múltiplo entero del ancho de la vista (cada celda, píxeles enteros)."""
    cells = box(view, scale)[2]
    return width > 0 and width % cells == 0


def snap_width(view, width, scale=SCALE):
    """El múltiplo válido más cercano hacia abajo (mínimo una celda por píxel)."""
    cells = box(view, scale)[2]
    return max(cells, width // cells * cells)
