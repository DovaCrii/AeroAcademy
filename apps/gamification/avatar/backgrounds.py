"""Fondos con dibujo por disciplina (pixel-art, mismo 32×32 que el avatar).

Los 8 primeros fondos de `palettes.BACKGROUNDS` son lisos. Los demás llevan un dibujo generado por una función pura
`(x, y) -> 0 | 1 | 2` (nada, tinta 1, tinta 2) sobre el color base. Todo es determinista y sale del catálogo.
"""

import math

PAD = 2  # el marco deja 2 celdas a cada lado del 32×32


def _hash(x, y):
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFF


def blueprint(x, y):
    """Plano: rejilla de cuadernillo con cotas arriba."""
    if y == 1 and 3 <= x <= 28:
        return 2 if x in (3, 28) or x % 5 == 3 else 1
    if x % 8 == 0 or y % 8 == 0:
        return 1 if (x + y) % 2 == 0 else 0
    return 0


def contour(x, y):
    """Curvas de nivel alrededor de una cima."""
    d = math.hypot((x - 24) * 1.0, (y - 7) * 1.5) + math.sin(x / 4.0) * 1.2
    ring = d % 6
    if ring < 1:
        return 2 if int(d) % 18 < 6 else 1
    return 0


def road(x, y):
    """Perfil longitudinal: terreno natural, rasante y estaciones."""
    ground = 22 + round(2.5 * math.sin(x / 4.5))
    grade = 21 - round(x / 12)
    if y == grade:
        return 2
    if y == ground:
        return 1
    if y > ground and (x + y) % 4 == 0:
        return 1
    if x % 8 == 0 and y < ground and y % 2 == 0:
        return 1
    return 0


def gears(x, y):
    """Engranajes grandes en las esquinas."""
    out = 0
    for cx, cy, r, teeth, ink in ((3, 27, 7.0, 10, 1), (28, 4, 6.0, 9, 2), (30, 29, 4.0, 7, 1)):
        d = math.hypot(x - cx, y - cy)
        angle = math.atan2(y - cy, x - cx)
        tooth = int((angle + math.pi) / (2 * math.pi) * teeth * 2) % 2 == 0
        outer = r + (1.6 if tooth else 0)
        if outer - 1.7 <= d <= outer or abs(d - r * 0.35) < 0.6:
            out = ink
    return out


def hud(x, y):
    """HUD de vuelo: esquinas, horizonte discontinuo y escalera de cabeceo."""
    for lx in (1, 30):
        for ly in (1, 30):
            if (abs(x - lx) <= 3 and y == ly) or (abs(y - ly) <= 3 and x == lx):
                return 2
    if y == 17 and x % 4 in (0, 1) and not 9 <= x <= 22:
        return 1
    if y in (11, 23) and (3 <= x <= 6 or 25 <= x <= 28):
        return 1
    if (x, y) in {(1, 17), (2, 17), (3, 17), (28, 17), (29, 17), (30, 17)}:
        return 2
    return 0


def pointcloud(x, y):
    """Nube de puntos: más densa abajo, de azul a ámbar según la cota."""
    h = _hash(x, y)
    density = 3 + (y * 14) // 32
    if h % 24 < density:
        return 2 if y < 9 and h % 5 == 0 else 1
    return 0


def iso(x, y):
    """Retícula isométrica de un modelo BIM."""
    if (x + y) % 8 == 0 or (x - y) % 8 == 0:
        return 1 if (x // 8 + y // 8) % 2 == 0 else 0
    if x % 16 == 8 and y % 8 in (0, 4):
        return 2
    return 0


def truss(x, y):
    """Cerchas arriba y abajo."""
    for base, flip in ((2, 1), (29, -1)):
        zig = abs(x % 8 - 4)
        if y in (base, base + flip * 4):
            return 1
        if y == base + flip * zig and 0 < zig < 4:
            return 2
    return 0


def gis(x, y):
    """Mapa urbano: calles, manzanas y un río."""
    river_y = 24 - round(x * 0.55 + 2 * math.sin(x / 3.0))
    if y in (river_y, river_y + 1):
        return 2
    if x % 9 == 2 or y % 8 == 3:
        return 1
    return 0


def hazard(x, y):
    """Franjas de seguridad amarillo y negro arriba y abajo."""
    if (y <= 2 or y >= 29) and (x + y) % 6 < 3:
        return 1
    return 0


PATTERNS = {
    "blueprint": (blueprint, "#2D6EB5", "#7CC4FF"),
    "contour": (contour, "#2F5E43", "#C9A24A"),
    "road": (road, "#4B5260", "#FF7A1A"),
    "gears": (gears, "#454C57", "#6D7886"),
    "hud": (hud, "#145A8C", "#4CC6FF"),
    "pointcloud": (pointcloud, "#2C6DD1", "#F5A524"),
    "iso": (iso, "#2E4778", "#4CC6FF"),
    "truss": (truss, "#4A5362", "#FFC21A"),
    "gis": (gis, "#1F6A66", "#4CC6FF"),
    "hazard": (hazard, "#FFC21A", "#FFC21A"),
}

# Índice de `palettes.BACKGROUNDS` → patrón. Los 8 primeros son lisos.
BY_INDEX = {
    8: "blueprint",
    9: "contour",
    10: "road",
    11: "gears",
    12: "hud",
    13: "pointcloud",
    14: "iso",
    15: "truss",
    16: "gis",
    17: "hazard",
}

# Disciplina → fondos que le calzan (para agruparlos y recomendarlos).
BY_DISCIPLINE = {
    "arquitectura": [8, 14, 0],
    "civil": [10, 15, 1],
    "topografia": [9, 16, 2],
    "mecanica": [11, 3, 5],
    "captura": [12, 13, 4],
    "transversal": [17, 13, 14, 6, 7],
}


def pattern_paths(index, lo=-PAD, hi=32 + PAD):
    """`[(color, d)]` con una ruta por tinta; vacío si el fondo es liso."""
    name = BY_INDEX.get(index)
    if not name:
        return []
    fn, ink1, ink2 = PATTERNS[name]
    runs = {ink1: [], ink2: []}
    for y in range(lo, hi):
        x = lo
        while x < hi:
            v = fn(x, y)
            if not v:
                x += 1
                continue
            run = 1
            while x + run < hi and fn(x + run, y) == v:
                run += 1
            runs[ink1 if v == 1 else ink2].append(f"M{x} {y}h{run}v1h-{run}z")
            x += run
    return [(color, "".join(segs)) for color, segs in runs.items() if segs]
