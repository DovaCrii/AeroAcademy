"""PROTOTIPO (no es código de producción) de la opción C de docs/AVATAR_RESOLUCION.md: híbrida 2× sobre el motor real.

Uso: python tools/proto_avatar_hd.py docs/img/avatar-res-comparacion.svg

compose_hd: cada capa del 32×32 se pinta ×2 en una grilla 64×64 (o se usa su versión HD si existe), con las mismas
reglas de encaje (cara, copa del gorro) escaladas; luego un pase procedural (contorno de 1 px, sombra y luz) y por
último el equipo HD en el escenario 80×80.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.gamification.avatar import backgrounds, engine  # noqa: E402
from apps.gamification.avatar.parts import body  # noqa: E402

OUT = sys.argv[1]
S, OX, OY = 80, 8, 12  # escenario HD 80×80; figura 64×64 en (8, 12)


def up(rows):
    out = {}
    for y, line in rows.items():
        wide = "".join(ch * 2 for ch in line)
        out[2 * y] = wide
        out[2 * y + 1] = wide
    return out


def paint(g, rows, only_on=None, dx=OX, dy=OY):
    for y, line in rows.items():
        for x, ch in enumerate(line):
            if ch == ".":
                continue
            X, Y = x + dx, y + dy
            if 0 <= X < S and 0 <= Y < S and (only_on is None or g[Y][X] in only_on):
                g[Y][X] = ch


def compose_hd(cfg, hd=None):
    hd = hd or {}
    g = [["."] * S for _ in range(S)]
    hair_art, hat_art = engine.HAIR[cfg["hair"]], engine.HEADWEAR[cfg["headwear"]]
    top = engine._hat_top(hat_art)
    opaque = cfg["glasses"] in engine.OPAQUE_GLASSES
    L = lambda r: up(r)  # noqa: E731
    paint(g, L(engine._above(hair_art["back"], top)))
    paint(g, L(hat_art["back"]))
    paint(g, L(body.BASE))
    paint(g, L(body.BODY_PATCH[cfg["body"]]))
    paint(g, L(body.LEGWEAR[cfg["legwear"]]))
    paint(g, L(engine.OUTFITS[cfg["outfit"]]), only_on={"O"})
    paint(g, L(engine.NECKWEAR[cfg["neckwear"]]))
    paint(g, L(engine.FACIAL_HAIR[cfg["facial_hair"]]))
    paint(g, hd.get("nose", L(body.NOSE)))
    paint(g, hd.get("mouth", L(engine.MOUTHS[cfg["mouth"]])))
    if not opaque:
        paint(g, L(engine.GLASSES[cfg["glasses"]]))
    paint(g, hd.get("eyes", L(engine.EYES[cfg["eyes"]])))
    paint(g, L(engine.BROWS[cfg["brows"]]))
    if opaque:
        paint(g, L(engine.GLASSES[cfg["glasses"]]))
    paint(g, L(engine._off_face(engine._above(hair_art["front"], top))))
    paint(g, L(engine._off_face(hat_art["front"])))
    detail_pass(g)
    for rows, x0, y0 in hd.get("overlays", []):
        paint(g, rows, dx=x0, dy=y0)
    halo(g)
    return g


SHADE = {"S": "s", "O": "o", "H": "j", "P": "p", "T": "t", "B": "b"}
LIGHT = {"S": "1", "O": "2", "H": "h", "P": "4", "T": "3"}


def detail_pass(g):
    """Contorno de 1 px por fuera, la mitad interior pasa a sombra; luz arriba-izquierda; esquinas redondeadas."""
    src = [row[:] for row in g]

    def at(x, y):
        return src[y][x] if 0 <= x < S and 0 <= y < S else "."

    for y in range(S):
        for x in range(S):
            ch = src[y][x]
            n4 = [at(x + 1, y), at(x - 1, y), at(x, y + 1), at(x, y - 1)]
            if ch == "K":
                if "." in n4:
                    # esquina exterior de un bloque 2×2: se recorta (redondea el escalón)
                    if (
                        at(x - 1, y) == "."
                        and at(x, y - 1) == "."
                        and at(x + 1, y) == "K"
                        and at(x, y + 1) == "K"
                        and at(x + 1, y + 1) not in ".K"
                    ):
                        g[y][x] = "."
                    continue
                # mitad interior del contorno exterior doble: arriba/izquierda → luz; abajo/derecha → sombra
                for (dx, dy), table in (
                    ((0, -1), LIGHT),
                    ((-1, 0), LIGHT),
                    ((0, 1), SHADE),
                    ((1, 0), SHADE),
                ):
                    if at(x + dx, y + dy) == "K" and at(x + 2 * dx, y + 2 * dy) == ".":
                        fill = at(x - dx, y - dy)
                        if fill in table:
                            g[y][x] = table[fill]
                        elif fill in SHADE:
                            g[y][x] = SHADE[fill]
                        break


def halo(g):
    src = [row[:] for row in g]
    for y in range(S):
        for x in range(S):
            if src[y][x] != ".":
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                X, Y = x + dx, y + dy
                if 0 <= X < S and 0 <= Y < S and src[Y][X] not in ".5":
                    g[y][x] = "5"
                    break


def lighten(hex_color, f=0.28):
    c = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(v + (255 - v) * f):02X}" for v in c)


def palette_hd(cfg):
    p = engine.palette_for(cfg)
    p.update(
        {
            "1": lighten(p["S"]),
            "2": lighten(p["O"]),
            "3": lighten(p["T"]),
            "4": lighten(p["P"]),
            "5": "#F4EBD8",
            "k": "#2B2F36",
            "I": "#C9D3DD",
            "V": "#7FE3FF",
        }
    )
    return p


def runs_svg(grid, palette, size_cells):
    by = {}
    for y, row in enumerate(grid):
        x = 0
        while x < size_cells:
            ch = row[x]
            if ch == ".":
                x += 1
                continue
            n = 1
            while x + n < size_cells and row[x + n] == ch:
                n += 1
            by.setdefault(palette[ch], []).append(f"M{x} {y}h{n}v1h-{n}z")
            x += n
    return "".join(f'<path fill="{c}" d="{"".join(s)}"/>' for c, s in by.items())


def hd_svg(cfg, hd, x, y, px):
    g = compose_hd(cfg, hd)
    pal = palette_hd(cfg)
    bg = engine.background_for(cfg)
    pat = "".join(
        f'<path fill="{c}" d="{d}"/>' for c, d in backgrounds.pattern_paths(cfg["background"])
    )
    ground = '<rect x="22" y="76" width="36" height="2" fill="#000" fill-opacity=".25"/>'
    body_svg = runs_svg(g, pal, S)
    return (
        f'<svg x="{x}" y="{y}" width="{px}" height="{px}" viewBox="0 0 {S} {S}" shape-rendering="crispEdges">'
        f'<rect width="{S}" height="{S}" fill="{bg}"/><g transform="scale(2.5)" opacity=".55">{pat}</g>'
        f"{ground}{body_svg}</svg>"
    ), len(body_svg)


def low_svg(cfg, x, y, px):
    inner = engine.render_svg(cfg, title="hoy")
    return inner.replace("<svg ", f'<svg x="{x}" y="{y}" width="{px}" height="{px}" ', 1)


# --- piezas HD de muestra (coordenadas del escenario 80×80) ------------------------------------------------------


def rows(*lines):
    return {i: line for i, line in enumerate(lines)}


EYES_DOT = rows(  # en coordenadas de la figura 64: ojos de 3×4 con brillo y párpado
    *["." * 64] * 22,
    "." * 24 + "KEE" + "." * 10 + "EEK" + "." * 27,
    "." * 24 + "EWE" + "." * 10 + "EWE" + "." * 27,
    "." * 24 + "EEE" + "." * 10 + "EEE" + "." * 27,
    "." * 24 + "EEE" + "." * 10 + "EEE" + "." * 27,
)
NOSE_HD = rows(*["." * 64] * 25, "." * 31 + "s" + "." * 32, "." * 31 + "ss" + "." * 31)
MOUTH_SMILE = rows(
    *["." * 64] * 28,
    "." * 26 + "K" + "." * 10 + "K" + "." * 26,
    "." * 27 + "KmmmmmmmmK" + "." * 27,
    "." * 28 + "KKKKKKKK" + "." * 28,
)

PRISM_POLE = rows(  # jalón de 4 px con franjas de 4, prisma redondo 10×9 con brillo (x 66..75)
    "...KKKK...",
    "..KYYYYK..",
    ".KYKKKKYK.",
    "KYKCWCCKYK",
    "KYKWCCCKYK",
    "KYKCCCCKYK",
    ".KYKKKKYK.",
    "..KYYYYK..",
    "...KDDK...",
    *(
        [
            "...KRRK...",
            "...KRRK...",
            "...KRRK...",
            "...KRRK...",
            "...KWWK...",
            "...KWWK...",
            "...KWWK...",
            "...KWWK...",
        ]
        * 8
    ),
    "...KZZK...",
    "....KK....",
)
DRONE = rows(  # dron 22×9 en el aire
    "ZZZZZZZ........ZZZZZZZ",
    "...KK............KK...",
    "...KK............KK...",
    "..KDDKKKKKKKKKKKKDDK..",
    "...KKDDDDDCCDDDDDKK...",
    ".....KDDDVVVVDDDK.....",
    "......KKDDQQDDKK......",
    "........K....K........",
    ".......KK....KK.......",
)
CONTROLLER = rows(  # control 16×10 con 2 palancas, pantalla V y antenas
    ".Z............Z.",
    ".Z............Z.",
    "KKKKKKKKKKKKKKKK",
    "KDDDDKKKKKKDDDDK",
    "KDKKDKVVVVKDKKDK",
    "KDKWDKVCCVKDKWDK",
    "KDDDDKVVVVKDDDDK",
    "KDRDDKKKKKKDDGDK",
    ".KDDDDDDDDDDDDK.",
    "..KKKKKKKKKKKK..",
)
TABLET = rows(  # tablet 14×12 con cubo BIM isométrico
    "KKKKKKKKKKKKKK",
    "KDDDDDDDDDDDDK",
    "KDVVVVCCVVVVDK",
    "KDVVVCWWCVVVDK",
    "KDVVCWWWWCVVDK",
    "KDVVKCWWCKVVDK",
    "KDVVKKCCKKVVDK",
    "KDVVVKKKKVVVDK",
    "KDVVVVKKVVVVDK",
    "KDVVVVVVVVVVDK",
    "KDDDDDZZDDDDDK",
    "KKKKKKKKKKKKKK",
)
PIN_THEO = rows("..YY..", ".KYYK.", "KYKKYK", ".KYYK.", ".Y..Y.", "Y....Y")
PATCH = rows("KKKKK", "KCCCK", "KCWCK", "KCCCK", "KKKKK")
HAND = rows(".KKK.", "KSSSK", "KSSSK", ".KKK.")

FACE = {"eyes": EYES_DOT, "nose": NOSE_HD, "mouth": MOUTH_SMILE}
CASES = [
    (
        "Geomensor/a · Topografía",
        "cartographer",
        {"eyes": "dot", "mouth": "smile", "glasses": "none", "skin": 3},
        {
            **FACE,
            "overlays": [(PRISM_POLE, 62, 2), (HAND, 60, 63), (PIN_THEO, 44, 54), (PATCH, 57, 56)],
        },
    ),
    (
        "Piloto de dron · Captura",
        "pilot",
        {
            "eyes": "dot",
            "mouth": "smile",
            "glasses": "none",
            "skin": 1,
            "hair": "ponytail",
            "body": "feminine",
        },
        {**FACE, "overlays": [(DRONE, 56, 1), (CONTROLLER, 32, 58), (PATCH, 17, 56)]},
    ),
    (
        "Ingeniero/a civil · Civil",
        "engineer",
        {
            "eyes": "dot",
            "mouth": "smile",
            "glasses": "none",
            "headwear": "hardhat",
            "skin": 5,
            "facial_hair": "beard",
            "body": "masculine",
        },
        {**FACE, "overlays": [(TABLET, 61, 52), (HAND, 59, 60), (PIN_THEO, 44, 54)]},
    ),
]


def main():
    W, H = 900, 1010
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        'font-family="Archivo, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#FAF8F3"/>',
        '<text x="24" y="38" font-size="22" font-weight="800" fill="#1B1F27">Avatar · resolución hoy vs. propuesta C (híbrida 2×)</text>',
        '<text x="24" y="62" font-size="13" fill="#4A5663">Generado con el motor real (compose + palette_for). Izquierda: render_svg de hoy (36 celdas) a 6× = 216 px. '
        "Derecha: prototipo HD 80×80 a 3× = 240 px:</text>",
        '<text x="24" y="80" font-size="13" fill="#4A5663">capas ×2 + pase procedural (contorno 1 px, sombra, luz, halo) + piezas HD de muestra (cara, equipo, pin, parche). '
        "Abajo: los dos a 1× y 2×.</text>",
    ]
    timings, sizes = [], []
    for i, (label, slug, extra, hd) in enumerate(CASES):
        cfg = engine.clean_config({**engine.apply_career({}, slug), **extra})
        y = 110 + i * 300
        out.append(
            f'<text x="24" y="{y}" font-size="15" font-weight="700" fill="#1B1F27">{label}</text>'
        )
        out.append(low_svg(cfg, 24, y + 12, 216))
        t = time.perf_counter()
        svg, n = hd_svg(cfg, hd, 270, y + 12, 240)
        timings.append((time.perf_counter() - t) * 1000)
        sizes.append((len(engine.render_svg(cfg)), len(svg)))
        out.append(svg)
        # tamaños chicos
        out.append(
            f'<text x="540" y="{y + 30}" font-size="12" fill="#4A5663">hoy 36 → 72 px (2×)</text>'
        )
        out.append(low_svg(cfg, 540, y + 40, 72))
        out.append(
            f'<text x="680" y="{y + 30}" font-size="12" fill="#4A5663">HD 80 → 80 px (1×) y 160 (2×)</text>'
        )
        out.append(hd_svg(cfg, hd, 680, y + 40, 80)[0])
        out.append(hd_svg(cfg, hd, 680, y + 128, 160)[0].replace('width="160"', 'width="160"'))
        out.append(
            f'<rect x="270" y="{y + 228}" width="44" height="18" fill="#FFC21A"/>'
            f'<text x="276" y="{y + 241}" font-size="11" font-weight="700" fill="#1B1F27">NV 7</text>'
        )
        out.append(
            f'<rect x="268" y="{y + 10}" width="244" height="244" fill="none" stroke="#8B5CF6" stroke-width="4"/>'
        )
    out.append(
        f'<text x="24" y="{H - 14}" font-size="11" fill="#4A5663">Marco y placa NV en CSS/HTML (no en el SVG). '
        f"SVG HD de la figura: {min(s[1] for s in sizes) // 1024}–{max(s[1] for s in sizes) // 1024} KB · hoy "
        f"{min(s[0] for s in sizes) // 1024}–{max(s[0] for s in sizes) // 1024} KB · render HD {max(timings):.1f} ms.</text>"
    )
    out.append("</svg>")
    open(OUT, "w", encoding="utf-8").write("\n".join(out))
    print("sizes", sizes, "ms", [round(t, 2) for t in timings])


main()
