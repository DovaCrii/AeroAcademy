"""Figura HD (docs/AVATAR_RESOLUCION.md, opción C): la grilla de 32 compuesta capa por capa ×2 en 64, dentro de un
escenario de 80×80, con un pase de acabado y piezas HD opcionales que reemplazan su capa ×2.

Este paquete no cambia ninguna opción ni índice: `render_svg(view="stage")` es función pura de la configuración
limpia (y de la pose de la vista previa). Una pieza sin versión HD se ve ×2; cada pieza HD se agrega por tandas.

Registro `HD`: `HD[categoría][id_de_opción]` es un sprite (o `{"front": sprite, "back": sprite}` en pelo y gorros).
  · un sprite es `sprite((x, y), ["fila", …])`, con las claves de la paleta del avatar y **sin** `1..5` (solo las pone
    el motor);
  · `space="figure"` (por defecto) ancla `(x, y)` en la figura de 64×64; `space="stage"` en el escenario de 80×80
    (equipo grande, dron y estación total viven aquí);
  · solo se aceptan ids que ya existen en `engine.CHOICES` (prueba `test_hd_ids_are_known_options`).
"""

from ..art import GRID
from ..views import STAGE

SCALE = 2  # cada celda de la grilla de 32 son 2×2 celdas HD
GRID_HD = GRID * SCALE  # 64: la figura
# Esquina de la figura dentro del escenario: aire arriba para antena y dron.
OFFSET = ((STAGE - GRID_HD) // 2, 12)
GROUND_Y = OFFSET[1] + GRID_HD  # primera fila bajo las botas: ahí va la sombra del suelo

# Categorías que pueden tener versión HD (clave de `engine.CHOICES` → ¿tiene frente y atrás?)
CATEGORIES = {
    "eyes": False,
    "brows": False,
    "mouth": False,
    "glasses": False,
    "facial_hair": False,
    "headwear": True,
    "hair": True,
    "outfit": False,
    "neckwear": False,
    "pin": False,
    "prop": False,
}
HD = {category: {} for category in CATEGORIES}

# Dónde puede dibujar cada categoría: `(x0, y0, x1, y1)` inclusivo, en el espacio de sus sprites (la figura de 64×64,
# salvo `prop`, que vive en el escenario de 80×80). Son las cajas de la grilla de 32 ×2 con un margen de una celda.
ZONES = {
    "eyes": (20, 18, 43, 29),
    "brows": (20, 14, 43, 21),
    "mouth": (22, 26, 41, 35),
    "glasses": (12, 14, 51, 29),
    "facial_hair": (18, 20, 45, 39),
    "headwear": (6, 0, 57, 29),
    "hair": (2, 0, 61, 54),
    "outfit": (8, 38, 55, 57),
    "neckwear": (18, 34, 45, 53),
    "pin": (36, 40, 47, 51),
    "prop": (0, 0, 79, 79),
}
MAX_COLORS = 12  # por sprite (skill sprite-8bit)


def sprite(at, rows, space="figure"):
    """Una pieza HD: filas de texto ancladas en `at` (`'.'` es transparente)."""
    if space not in {"figure", "stage"}:
        raise ValueError(f"espacio desconocido: {space!r}")
    return {"at": tuple(at), "rows": list(rows), "space": space}


def up2(rows):
    """Una pieza de la grilla de 32 (`{y: "32 caracteres"}`) escalada ×2 a la grilla de 64."""
    out = {}
    for y, line in rows.items():
        wide = "".join(ch * SCALE for ch in line)
        for dy in range(SCALE):
            out[y * SCALE + dy] = wide
    return out
