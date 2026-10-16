"""`compose_hd`: la figura HD (64×64) dentro del escenario (80×80), con el mismo orden de capas y las mismas reglas
que `engine.compose` (la ventana de la cara, la copa del gorro, la ropa solo sobre `O`).

Cada capa usa su versión HD si existe (`hd.HD[categoría][id]`); si no, la pieza de 32 escalada ×2. Es función pura
de la configuración ya limpia y de la pose.
"""

from .. import engine
from ..parts import body, poses
from . import HD, OFFSET, SCALE, STAGE, up2
from .detail import detail_pass

OX, OY = OFFSET
# Ventana de la cara en el escenario: ni el pelo ni un gorro dibujan aquí.
FACE_X = range(OX + engine.FACE_X.start * SCALE, OX + engine.FACE_X.stop * SCALE)
FACE_Y = range(OY + engine.FACE_Y.start * SCALE, OY + engine.FACE_Y.stop * SCALE)


def blank():
    return [["."] * STAGE for _ in range(STAGE)]


def _put(grid, x, y, ch, only_on=None):
    if 0 <= x < STAGE and 0 <= y < STAGE and (only_on is None or grid[y][x] in only_on):
        grid[y][x] = ch


def _paint_rows(grid, rows, only_on=None):
    """Filas de la figura de 64×64 (coordenadas de la figura)."""
    for y, line in rows.items():
        for x, ch in enumerate(line):
            if ch != ".":
                _put(grid, x + OX, y + OY, ch, only_on)


def _paint_sprite(grid, art, only_on=None, clip_face=False):
    x0, y0 = art["at"]
    if art["space"] == "figure":
        x0, y0 = x0 + OX, y0 + OY
    for j, line in enumerate(art["rows"]):
        for i, ch in enumerate(line):
            if ch == "." or (clip_face and x0 + i in FACE_X and y0 + j in FACE_Y):
                continue
            _put(grid, x0 + i, y0 + j, ch, only_on)


def _layer(grid, category, option, rows, *, part=None, only_on=None, clip_face=False):
    """Pinta la versión HD de la opción si existe y, si no, la pieza de 32 ×2."""
    art = HD[category].get(option)
    if art is not None:
        art = art[part] if part else art
        pieces = art if isinstance(art, list) else [art]  # el equipo grande puede ser varias piezas
        for piece in pieces:
            if piece:
                _paint_sprite(grid, piece, only_on, clip_face)
        return
    _paint_rows(grid, up2(rows), only_on)


def _apply_pose(grid, patch):
    """Reemplaza celdas del cuerpo (un `.` las vacía): así el brazo cambia de lugar."""
    for y, (x0, chars) in patch.items():
        for i, ch in enumerate(chars):
            for dy in range(SCALE):
                for dx in range(SCALE):
                    X, Y = OX + (x0 + i) * SCALE + dx, OY + y * SCALE + dy
                    if 0 <= X < STAGE and 0 <= Y < STAGE:
                        grid[Y][X] = ch


def compose_layers(cfg, pose=poses.DEFAULT_POSE):
    """Las capas sin el pase de acabado (la figura ×2 o con piezas HD, ya en el escenario)."""
    grid = blank()
    hair_art, hat_art = engine.HAIR[cfg["hair"]], engine.HEADWEAR[cfg["headwear"]]
    top = engine._hat_top(hat_art)
    opaque = cfg["glasses"] in engine.OPAQUE_GLASSES

    _layer(grid, "hair", cfg["hair"], engine._above(hair_art["back"], top), part="back")
    _layer(grid, "headwear", cfg["headwear"], hat_art["back"], part="back")
    _paint_rows(grid, up2(body.BASE))
    _paint_rows(grid, up2(body.BODY_PATCH[cfg["body"]]))
    _apply_pose(grid, poses.POSES.get(pose, {}))
    _paint_rows(grid, up2(body.LEGWEAR[cfg["legwear"]]))
    _layer(grid, "outfit", cfg["outfit"], engine.OUTFITS[cfg["outfit"]], only_on={"O"})
    _layer(grid, "neckwear", cfg["neckwear"], engine.NECKWEAR[cfg["neckwear"]])
    _layer(grid, "facial_hair", cfg["facial_hair"], engine.FACIAL_HAIR[cfg["facial_hair"]])
    _layer(grid, "nose", "default", body.NOSE)
    _layer(grid, "mouth", cfg["mouth"], engine.MOUTHS[cfg["mouth"]])
    if not opaque:
        _layer(grid, "glasses", cfg["glasses"], engine.GLASSES[cfg["glasses"]])
    _layer(grid, "eyes", cfg["eyes"], engine.EYES[cfg["eyes"]])
    _layer(grid, "brows", cfg["brows"], engine.BROWS[cfg["brows"]])
    if opaque:
        _layer(grid, "glasses", cfg["glasses"], engine.GLASSES[cfg["glasses"]])
    front = engine._off_face(engine._above(hair_art["front"], top))
    _layer(grid, "hair", cfg["hair"], front, part="front", clip_face=True)
    _layer(
        grid,
        "headwear",
        cfg["headwear"],
        engine._off_face(hat_art["front"]),
        part="front",
        clip_face=True,
    )
    _layer(grid, "pin", cfg["pin"], engine.PINS[cfg["pin"]])
    _layer(grid, "prop", cfg["prop"], engine.PROPS[cfg["prop"]])
    return grid


def compose_hd(cfg, pose=poses.DEFAULT_POSE):
    """Matriz 80×80 de claves de color ('.' = transparente): capas + acabado."""
    return detail_pass(compose_layers(cfg, pose))
