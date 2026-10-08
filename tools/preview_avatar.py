"""Genera una imagen PNG para VER el avatar mientras se dibuja una pieza (sin dependencias).

Uso (desde la raíz del repositorio):
    python tools/preview_avatar.py salida.png                               # avatar por defecto
    python tools/preview_avatar.py salida.png hair=long hair_color=3 body=feminine
    python tools/preview_avatar.py salida.png --sheet hair                  # hoja con TODOS los estilos de una categoría
    python tools/preview_avatar.py salida.png --matrix glasses eyes         # cruza dos categorías (filas × columnas)
Categorías de --sheet: hair, eyes, brows, mouth, facial_hair, glasses, headwear, outfit, neckwear.
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


def render_pixels(cfg):
    cfg = engine.clean_config(cfg)
    grid, palette = engine.compose(cfg), engine.palette_for(cfg)
    bg = hex_rgb(engine.background_for(cfg))
    return [[hex_rgb(palette[ch]) if ch != "." else bg for ch in row] for row in grid]


def write_png(path, tiles, scale, cols):
    rows_n = (len(tiles) + cols - 1) // cols
    gap = 2
    width = cols * (GRID * scale + gap) + gap
    height = rows_n * (GRID * scale + gap) + gap
    canvas = [[(24, 28, 38)] * width for _ in range(height)]
    for index, pixels in enumerate(tiles):
        ox = gap + (index % cols) * (GRID * scale + gap)
        oy = gap + (index // cols) * (GRID * scale + gap)
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
    scale, cfg, sheet, matrix = 6, {}, None, None
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--sheet":
            sheet = rest[i + 1]
            i += 1
        elif arg == "--matrix":
            matrix = (rest[i + 1], rest[i + 2])
            i += 2
        elif "=" in arg:
            key, value = arg.split("=", 1)
            if key == "scale":
                scale = int(value)
            else:
                cfg[key] = int(value) if value.lstrip("-").isdigit() else value
        i += 1
    if matrix:
        rows_key, cols_key = matrix
        tiles = [
            render_pixels({**cfg, rows_key: r, cols_key: c})
            for r in engine.CHOICES[rows_key]
            for c in engine.CHOICES[cols_key]
        ]
        write_png(out, tiles, scale, cols=len(engine.CHOICES[cols_key]))
    elif sheet:
        if sheet not in engine.CHOICES:
            print("categoría desconocida:", sheet, "· válidas:", ", ".join(engine.CHOICES))
            return 2
        tiles = [render_pixels({**cfg, sheet: option}) for option in engine.CHOICES[sheet]]
        write_png(out, tiles, scale, cols=min(7, len(tiles)))
    else:
        write_png(out, [render_pixels(cfg)], scale, cols=1)
    print("escrito", out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
