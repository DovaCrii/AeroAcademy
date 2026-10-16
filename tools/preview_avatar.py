"""Genera una imagen PNG para VER el avatar mientras se dibuja una pieza (sin dependencias).

Uso (desde la raíz del repositorio):
    python tools/preview_avatar.py salida.png                               # avatar por defecto
    python tools/preview_avatar.py salida.png hair=long hair_color=3 body=feminine
    python tools/preview_avatar.py salida.png --sheet hair                  # hoja con TODOS los estilos de una categoría
    python tools/preview_avatar.py salida.png --matrix glasses eyes         # cruza dos categorías (filas × columnas)
Categorías de --sheet: hair, eyes, brows, mouth, facial_hair, glasses, headwear, outfit, neckwear, prop, pin.
Con --hd se dibuja el escenario HD de 80×80 (figura de 64 con acabado, halo y sombra) en lugar del 32×32:
    python tools/preview_avatar.py salida.png --hd --sheet headwear scale=3 background=18
    python tools/preview_avatar.py salida.png --hd --careers cartographer pilot engineer scale=3
Con badge=epic se ve el parche y el adhesivo de esa rareza. Con pose=wave se ve una pose (solo vista previa). `--careers` dibuja cada carrera con su look sobre fondo oscuro y
sobre papel (hoja de contactos para revisar a la vez).
Opciones: scale=N (por defecto 6) y cualquier clave de configuración (ver DEFAULTS en el motor).
"""

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.gamification.avatar import engine  # noqa: E402
from apps.gamification.avatar.art import GRID  # noqa: E402


def png_bytes(width, height, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag, data):
        body = tag + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def render_pixels(cfg, hd=False, pose="stand", badge=None):
    cfg = engine.clean_config(cfg)
    if hd:
        from apps.gamification.avatar.hd.compose import compose_hd
        from apps.gamification.avatar.hd.render import SHADOW, palette_hd

        grid, palette = compose_hd(cfg, pose, badge), palette_hd(cfg, badge)
        bg_hex = engine.background_for(cfg)
        bg = hex_rgb(bg_hex)
        pixels = [[bg] * len(grid) for _ in grid]
        shadow = (
            hex_rgb("#000000")
            if engine.halo_color(bg_hex) == engine.HALO_LIGHT
            else hex_rgb(engine.HALO_DARK)
        )
        for y, x0, x1 in SHADOW:  # sombra del suelo (mezcla simple con el fondo)
            for x in range(x0, x1):
                pixels[y][x] = tuple((a * 4 + b) // 5 for a, b in zip(bg, shadow, strict=True))
        halo = hex_rgb(engine.halo_color(bg_hex))
        for x, y in engine.halo_cells(grid):
            pixels[y][x] = halo
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch != ".":
                    pixels[y][x] = hex_rgb(palette[ch])
        return pixels
    grid, palette = engine.compose(cfg), engine.palette_for(cfg)
    bg = hex_rgb(engine.background_for(cfg))
    return [[hex_rgb(palette[ch]) if ch != "." else bg for ch in row] for row in grid]


def write_png(path, tiles, scale, cols, cells=GRID):
    rows_n = (len(tiles) + cols - 1) // cols
    gap = 2
    width = cols * (cells * scale + gap) + gap
    height = rows_n * (cells * scale + gap) + gap
    canvas = [[(24, 28, 38)] * width for _ in range(height)]
    for index, pixels in enumerate(tiles):
        ox = gap + (index % cols) * (cells * scale + gap)
        oy = gap + (index // cols) * (cells * scale + gap)
        for y, row in enumerate(pixels):
            for x, color in enumerate(row):
                for dy in range(scale):
                    line = canvas[oy + y * scale + dy]
                    for dx in range(scale):
                        line[ox + x * scale + dx] = color
    flat = [[c for px in line for c in px] for line in canvas]
    Path(path).write_bytes(png_bytes(width, height, flat))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out, rest = argv[0], argv[1:]
    scale, cfg, sheet, matrix, hd, careers, pose, badge = (
        6,
        {},
        None,
        None,
        False,
        None,
        "stand",
        None,
    )
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--sheet":
            sheet = rest[i + 1]
            i += 1
        elif arg == "--hd":
            hd = True
        elif arg == "--careers":
            careers = []
            while i + 1 < len(rest) and "=" not in rest[i + 1] and not rest[i + 1].startswith("--"):
                careers.append(rest[i + 1])
                i += 1
        elif arg == "--matrix":
            matrix = (rest[i + 1], rest[i + 2])
            i += 2
        elif "=" in arg:
            key, value = arg.split("=", 1)
            if key == "scale":
                scale = int(value)
            elif key == "pose":
                pose = value
            elif key == "badge":
                badge = value  # rareza del parche y el adhesivo: common, rare, epic o legendary
            else:
                cfg[key] = int(value) if value.lstrip("-").isdigit() else value
        i += 1
    cells = 80 if hd else GRID
    if hd and scale == 6:
        scale = 3
    if careers:
        slugs = careers or list(engine.CLASSES)
        tiles = []
        for background in (None, 18):  # oscuro (el de su look) y papel
            for entry in slugs:
                slug, _, prop = entry.partition(
                    ":"
                )  # «carrera:herramienta» cambia la herramienta del look
                look = engine.apply_career({}, slug)
                if prop:
                    look["prop"] = prop
                look.update(cfg)
                if background is not None and "background" not in cfg:
                    look["background"] = background
                tiles.append(render_pixels(look, hd, pose, badge))
        write_png(out, tiles, scale, cols=len(slugs), cells=cells)
    elif matrix:
        rows_key, cols_key = matrix
        tiles = [
            render_pixels({**cfg, rows_key: r, cols_key: c}, hd, pose, badge)
            for r in engine.CHOICES[rows_key]
            for c in engine.CHOICES[cols_key]
        ]
        write_png(out, tiles, scale, cols=len(engine.CHOICES[cols_key]), cells=cells)
    elif sheet:
        if sheet not in engine.CHOICES:
            print("categoría desconocida:", sheet, "· válidas:", ", ".join(engine.CHOICES))
            return 2
        tiles = [
            render_pixels({**cfg, sheet: option}, hd, pose, badge)
            for option in engine.CHOICES[sheet]
        ]
        write_png(out, tiles, scale, cols=min(7, len(tiles)), cells=cells)
    else:
        write_png(out, [render_pixels(cfg, hd, pose, badge)], scale, cols=1, cells=cells)
    print("escrito", out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
