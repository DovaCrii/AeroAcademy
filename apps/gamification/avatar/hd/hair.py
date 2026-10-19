"""Pelo HD (fase 2): los 16 peinados con pelo (todos menos «Calvo»), frente y atrás, a la resolución de la figura de 64×64.

Cada peinado parte de su pieza de 32 escalada ×2 (misma silueta, mismo borde, misma regla de la cara y de la copa del
gorro) y le dibuja encima la **textura del pelo**: mechones que siguen el sentido del peinado (radiales desde la coronilla
o la raya, verticales, ondulados, trenzados en espiga, rizos en celdas), un brillo en forma de franja arriba a la izquierda
(la luz del pase de acabado), la sombra del flequillo sobre la frente y la sombra de las puntas. Una celda de **contorno
nunca se toca** y una celda vacía nunca se llena: la silueta del peinado grande es la de la miniatura de 32.

Colores: solo los tres tonos del color de pelo elegido (`H` base, `h` luz, `j` sombra) y el contorno `K`; nada fuera de
`palettes.HAIR_COLORS`. Las líneas se mueven de a dos filas (como un dibujo ×2), así el SVG junta las corridas y pesa poco.
Zona: x 2..61 · y 0..54. Cada textura es una función pura de la celda: el resultado es determinista.
"""

import math

from .. import engine
from . import HD, sprite, up2

FILL = "Hhj"


# --- utilidades -------------------------------------------------------------------------------------------------------


def _rnd(x, y, salt=0):
    """Número pseudoaleatorio estable en [0, 1) de una celda (sin `random`: el dibujo no cambia nunca)."""
    n = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535


class Cell:
    """Contexto de una celda de relleno: su lugar en la fila y la columna del relleno y el símbolo que tenía en el 32."""

    __slots__ = ("up", "left", "down", "right", "orig", "span")

    def __init__(self, up, left, down, right, orig, span):
        self.up, self.left, self.down, self.right, self.orig, self.span = (
            up,
            left,
            down,
            right,
            orig,
            span,
        )


def _context(rows, low):
    """Para cada celda de relleno: cuántas celdas de relleno hay hasta el borde en cada sentido (1 = al borde)."""
    ys = sorted(rows)
    fill = {(x, y) for y in ys for x, ch in enumerate(rows[y]) if ch in FILL}
    ctx = {}
    for x, y in fill:
        up = left = down = right = 1
        while (x, y - up) in fill:
            up += 1
        while (x - left, y) in fill:
            left += 1
        while (x, y + down) in fill:
            down += 1
        while (x + right, y) in fill:
            right += 1
        orig = low.get(y // 2, "." * 32)[x // 2]
        ctx[(x, y)] = Cell(up, left, down, right, orig, left + right - 1)
    return ctx


def _finish(tone, c, x, y):
    """Remate común: sombra en las puntas y bajo el flequillo, luz en el borde de arriba y de la izquierda."""
    if tone == "H":
        if c.down <= 1 or c.right <= 1:
            return "j"
        if c.up == 1 or c.left == 1:
            return "h"
    return tone


def _strand(u, lit, salt):
    """Un mechón: línea oscura de ancho variable y, si hay luz, cuerpo claro entero o solo junto a la línea."""
    i = math.floor(u)
    fr = u - i
    width = 0.2 + 0.26 * _rnd(i, 3, salt)
    if fr < width:
        return (
            "j" if _rnd(i, 5, salt) > 0.12 else "H"
        )  # algún mechón sin raya: se funde con el vecino
    if lit:
        whole = _rnd(i, 9, salt) < 0.35
        if whole or fr < width + 0.36:
            return "h"
    return "H"


def _sheen(cx, cy, rx, ry):
    """Franja de luz: elipse arriba a la izquierda; adentro los mechones claros se ven."""

    def lit(x, y):
        return ((x + 0.5 - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1

    return lit


def radial(sx, sy, n, sheen, keep_j=False, salt=1):
    """Mechones que salen de un punto (la coronilla o la raya): `n` mechones por media vuelta."""

    def tone(x, y, c):
        if keep_j and c.orig == "j" and x % 2 == 0:
            return "j"
        yq = y - (y & 1)
        dx, dy = x + 0.5 - sx, yq - sy
        u = math.atan2(dx, dy) / math.pi * n
        return _finish(_strand(u, sheen(x, y), salt), c, x, y)

    return tone


def vertical(pitch, amp, wavelength, sheen, mirror=True, phase=0.0, tilt=0.0, salt=2, step=2):
    """Mechones verticales (opcionalmente ondulados) que se abren desde el centro de la cabeza."""

    def tone(x, y, c):
        yq = y - (y % step)  # la ondulación se mueve de a `step` filas: el SVG junta las corridas
        base = abs(x + 0.5 - 32) if mirror else x + 0.5
        u = (base + amp * math.sin(yq * 2 * math.pi / wavelength + phase) + tilt * yq) / pitch
        return _finish(_strand(u, sheen(x, y), salt), c, x, y)

    return tone


def swept(dx, dy, pitch, sheen, keep_j=False, salt=3):
    """Mechones paralelos que siguen la dirección (dx, dy): jopo, tail, cola."""
    norm = math.hypot(dx, dy)
    nx, ny = dy / norm, -dx / norm

    def tone(x, y, c):
        if keep_j and c.orig == "j" and x % 2 == 0:
            return "j"
        yq = y - (y & 1)
        u = ((x + 0.5) * nx + yq * ny) / pitch
        return _finish(_strand(u, sheen(x, y), salt), c, x, y)

    return tone


def curls(radius, ox, oy, sheen):
    """Rizos: una red de celdas redondas con un hueco oscuro entre ellas y un brillo en cada una."""
    step_x, step_y = radius * 1.8, radius * 1.55

    def tone(x, y, c):
        yq = y - (y & 1)
        row = round((yq - oy) / step_y)
        best = 9.0
        for j in (row - 1, row, row + 1):
            shift = (j % 2) * step_x / 2
            i = round((x + 0.5 - ox - shift) / step_x)
            for k in (i - 1, i, i + 1):
                cx, cy = ox + k * step_x + shift, oy + j * step_y
                dx, dy = x + 0.5 - cx, yq - cy
                d = math.hypot(dx, dy) / radius
                if d < best:
                    best, bdx, bdy = d, dx, dy
        if best > 0.8:
            return "j"
        if (bdx + bdy) < -0.18 * radius and best > 0.3 and sheen(x, y):
            return "h"
        return _finish("H", c, x, y) if c.down <= 1 else "H"

    return tone


def plait(pitch, sheen, step=2):
    """Trenza: espiga de líneas en «V» centrada en cada tramo de la fila."""

    def tone(x, y, c):
        yq = y - (y % step)
        centre = x + 0.5 - c.left + c.span / 2
        u = (yq + abs(x + 0.5 - centre) * 1.6) / pitch
        fr = u - math.floor(u)
        if fr < 0.3:
            return "j"
        if fr < 0.62 and sheen(x, y):
            return "h"
        return "H"

    return tone


def spiral(cx, cy, turns, pitch, sheen):
    """Moño: mechones que se enroscan alrededor del centro de la bola."""

    def tone(x, y, c):
        yq = y - (y & 1)
        dx, dy = x + 0.5 - cx, yq - cy
        r = math.hypot(dx, dy)
        u = math.atan2(dx, dy) / (2 * math.pi) * turns + r / pitch
        return _finish(_strand(u, sheen(x, y), 4), c, x, y)

    return tone


def stubble(dark, light, salt=1):
    """Pelo rapado: puntos de luz y sombra repartidos sin patrón visible."""

    def tone(x, y, c):
        v = _rnd(x, y // 2, salt)
        if v < dark:
            return "j"
        if v > 1 - light:
            return "h"
        return "H"

    return tone


def tied(base, tie_y, tie_h=2):
    """Una textura con una liga: franja oscura de `tie_h` filas desde `tie_y` y luz justo debajo."""

    def tone(x, y, c):
        if tie_y <= y < tie_y + tie_h:
            return "j"
        if y == tie_y + tie_h:
            return "h"
        return base(x, y, c)

    return tone


def by_region(*regions):
    """Une texturas por zona: `(predicado, textura)`; la primera que acepta la celda gana."""

    def tone(x, y, c):
        for test, fn in regions:
            if test(x, y, c):
                return fn(x, y, c)
        return "H"

    return tone


def _shaved(c):
    return c.orig == "j"


# --- una textura por peinado ------------------------------------------------------------------------------------------

# Las luces se dibujan arriba a la izquierda (misma luz que el pase de acabado).
CROWN = _sheen(26, 14, 9, 5)  # sobre la frente y la coronilla
CROWN_HIGH = _sheen(27, 8, 9, 5)  # peinados altos (jopo, mohicano, moño)
SIDE_L = _sheen(18, 40, 6, 14)  # pelo largo: franja en el lado izquierdo
SIDE_R = _sheen(46, 40, 6, 14)  # y tenue en el derecho

STYLES = {
    "buzz": {"front": stubble(0.34, 0.16, 3)},
    "short": {"front": radial(31.5, 6, 14, CROWN)},
    "side_part": {"front": radial(25, 3, 17, _sheen(34, 10, 11, 4), keep_j=True)},
    "quiff": {"front": swept(0.6, -0.8, 3.8, CROWN_HIGH, keep_j=True)},
    "curly": {
        "front": curls(6.0, 12, 4, _sheen(26, 10, 14, 8)),
        "back": curls(6.0, 9, 22, SIDE_L),
    },
    "afro": {
        "front": curls(5.2, 4, 3, _sheen(24, 12, 16, 9)),
        "back": curls(5.2, 6, 20, _sheen(14, 28, 9, 12)),
    },
    "long": {
        "front": by_region(
            (lambda x, y, c: y < 26, radial(31.5, 4, 14, CROWN)),
            (lambda x, y, c: True, vertical(3.4, 0.8, 22, SIDE_L, phase=0.8, step=4)),
        ),
        "back": vertical(3.8, 1.0, 20, _sheen(18, 28, 6, 14), phase=0.4, step=4),
    },
    "wavy": {
        "front": by_region(
            (lambda x, y, c: y < 22, radial(31.5, 4, 13, CROWN)),
            (lambda x, y, c: True, vertical(4.8, 1.0, 24, SIDE_L, phase=0.0, step=6)),
        ),
        "back": vertical(5.0, 1.0, 24, _sheen(16, 28, 6, 12), phase=1.6, step=6),
    },
    "ponytail": {
        "front": radial(31.5, 6, 14, CROWN),
        "back": tied(swept(0.28, 1.0, 3.0, _sheen(50, 26, 5, 12)), tie_y=10),
    },
    "bun": {
        "front": by_region(
            (lambda x, y, c: y < 12, spiral(31.5, 6, 2.0, 2.4, CROWN_HIGH)),
            (lambda x, y, c: True, radial(31.5, 10, 14, CROWN)),
        ),
    },
    "bob": {
        "front": by_region(
            (lambda x, y, c: y < 20, radial(31.5, 5, 14, CROWN)),
            (lambda x, y, c: True, vertical(3.6, 0.5, 20, SIDE_L)),
        ),
        "back": vertical(3.6, 0.5, 20, SIDE_L),
    },
    "braids": {
        "front": by_region(
            (lambda x, y, c: y < 18, radial(31.5, 6, 14, CROWN)),
            (lambda x, y, c: True, plait(6.0, _sheen(15, 36, 5, 16), step=4)),
        ),
    },
    "mohawk": {
        "front": by_region(
            (lambda x, y, c: _shaved(c), stubble(0.45, 0.1, 5)),
            (lambda x, y, c: True, vertical(2.6, 0.0, 10, _sheen(29, 8, 5, 8))),
        ),
    },
    "flat_top": {"front": vertical(2.8, 0.0, 10, _sheen(27, 8, 9, 5))},
    "pixie": {
        "front": by_region(
            (lambda x, y, c: y >= 20, vertical(3.0, 0.5, 16, CROWN)),
            (lambda x, y, c: True, radial(36, 6, 13, CROWN, keep_j=False)),
        ),
    },
    "undercut": {
        "front": by_region(
            (lambda x, y, c: _shaved(c), stubble(0.5, 0.08, 9)),
            (lambda x, y, c: True, swept(0.7, -0.7, 3.6, CROWN_HIGH)),
        ),
    },
}


# --- construcción -----------------------------------------------------------------------------------------------------


def _texture(low, fn):
    """Pieza de 32 → sprite HD: ×2 y textura sobre cada celda de relleno; el contorno y los huecos no se tocan."""
    rows = {y: list(line) for y, line in up2(low).items()}
    if not any(ch != "." for line in rows.values() for ch in line):
        return None
    ctx = _context({y: "".join(line) for y, line in rows.items()}, low)
    for (x, y), cell in ctx.items():
        rows[y][x] = fn(x, y, cell)
    ys = sorted(y for y, line in rows.items() if any(ch != "." for ch in line))
    xs = [x for y in ys for x, ch in enumerate(rows[y]) if ch != "."]
    x0, x1 = min(xs), max(xs)
    return sprite(
        (x0, ys[0]),
        [
            "".join(rows[y][x0 : x1 + 1]) if y in rows else "." * (x1 - x0 + 1)
            for y in range(ys[0], ys[-1] + 1)
        ],
    )


def _style(option, textures):
    art = engine.HAIR[option]
    out = {}
    for layer in ("front", "back"):
        if art[layer]:
            assert layer in textures, f"el peinado «{option}» ({layer}) no tiene textura"
        out[layer] = _texture(art[layer], textures[layer]) if layer in textures else None
    return out


HD["hair"].update({option: _style(option, textures) for option, textures in STYLES.items()})
