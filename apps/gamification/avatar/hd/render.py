"""SVG del escenario HD (80×80): fondo con su dibujo, sombra del suelo, halo y la figura, un `<path>` por color."""

import json
from functools import lru_cache

from .. import backgrounds, engine, palettes
from ..parts import poses
from . import GROUND_Y, STAGE
from .compose import compose_hd

# El dibujo de los fondos (grilla de 32) se agranda al escenario sin salir de la grilla.
BACKGROUND_SCALE = 2.5
# Sombra elíptica bajo las botas: (fila, x0, x1)
SHADOW = ((GROUND_Y + 1, 24, 56), (GROUND_Y + 2, 28, 52))


def lighten(hex_color, amount=0.28):
    channels = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in channels)


def palette_hd(cfg, badge=None):
    """La paleta del avatar más los tonos de luz que solo pone el motor (`1` piel, `2` ropa, `3` gorro, `4` pantalón)."""
    palette = engine.palette_for(cfg)
    palette.update(
        {
            "1": lighten(palette["S"]),
            "2": lighten(palette["O"]),
            "3": lighten(palette["T"]),
            "4": lighten(palette["P"]),
        }
    )
    if badge:
        palette["6"] = engine.BADGE_COLORS[badge]
    return palette


def _shadow(background_hex):
    """Sombra del suelo: negra al 20 % en fondos oscuros y tinta al 13 % en claros."""
    dark = engine.contrast(engine.HALO_LIGHT, background_hex) >= engine.contrast(
        engine.HALO_DARK, background_hex
    )
    color, opacity = ("#000000", ".2") if dark else (engine.HALO_DARK, ".13")
    d = "".join(f"M{x0} {y}h{x1 - x0}v1h-{x1 - x0}z" for y, x0, x1 in SHADOW)
    return f'<path fill="{color}" fill-opacity="{opacity}" d="{d}"/>'


def _backdrop(index, halo, pattern, rect):
    color = palettes.BACKGROUNDS[index][1]
    out = [f'<rect width="{STAGE}" height="{STAGE}" fill="{color}"/>'] if rect else []
    if pattern:
        for ink, d in backgrounds.pattern_paths(index, 0, 0, STAGE, STAGE, scale=BACKGROUND_SCALE):
            out.append(f'<path fill="{ink}" d="{d}"/>')
    out.append(_shadow(color))
    rows = {}
    for x, y in halo:
        rows.setdefault(y, []).append(x)
    if rows:
        out.append(f'<path fill="{engine.halo_color(color)}" d="{engine._runs(rows, 0, STAGE)}"/>')
    return "".join(out)


@lru_cache(maxsize=512)
def _stage_body(cfg_key, bg_alt, pose, pattern, halo, rect, badge=None):
    """Todo lo que va dentro del `<svg>`: es el mismo para la misma configuración, así que se guarda en caché."""
    cfg = json.loads(cfg_key)
    grid = compose_hd(cfg, pose, badge)
    outline = engine.halo_cells(grid) if halo else []
    dark = _backdrop(cfg["background"], outline, pattern, rect)
    if bg_alt is None or bg_alt == cfg["background"]:
        parts = [dark]
    else:
        light = _backdrop(bg_alt, outline, pattern, rect)
        parts = [f'<g class="av-bg-dark">{dark}</g><g class="av-bg-light">{light}</g>']
    palette = palette_hd(cfg, badge)
    by_color = {}
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != ".":
                by_color.setdefault(palette[ch], {}).setdefault(y, []).append(x)
    for color, rows in by_color.items():
        parts.append(f'<path fill="{color}" d="{engine._runs(rows, 0, STAGE)}"/>')
    return "".join(parts)


def render_stage(
    cfg,
    *,
    title="Avatar",
    pose=poses.DEFAULT_POSE,
    decorative=False,
    bg_alt=None,
    pattern=True,
    halo=True,
    inline=False,
    backdrop=True,
    badge=None,
):
    """SVG del escenario HD para una configuración ya limpia."""
    pose = pose if pose in poses.POSES else poses.DEFAULT_POSE
    body = _stage_body(
        json.dumps(cfg, sort_keys=True), bg_alt, pose, pattern, halo, backdrop, badge
    )
    ns = "" if inline else ' xmlns="http://www.w3.org/2000/svg"'
    if decorative:
        crisp = "" if inline else ' shape-rendering="crispEdges"'
        head = f'<svg{ns} viewBox="0 0 {STAGE} {STAGE}"{crisp} aria-hidden="true">'
    else:
        head = (
            f'<svg{ns} viewBox="0 0 {STAGE} {STAGE}" shape-rendering="crispEdges" role="img" '
            f'aria-label="{engine._esc(title)}"><title>{engine._esc(title)}</title>'
        )
    return f"{head}{body}</svg>"
