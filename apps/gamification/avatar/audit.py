"""Reglas de compatibilidad entre piezas del avatar. Las usan `tools/audit_avatar.py` y las pruebas.

Se comprueban pares de piezas (no todas las combinaciones, que son cientos de miles) con los valores
"peores casos" del resto: así se detecta cualquier choque sin recorrer el producto completo.
"""

from . import engine
from .art import GRID
from .parts import face

# Ventana de la cara donde ningún gorro ni peinado debe tapar ojos, nariz ni boca.
FACE_WINDOW = (engine.FACE_X, engine.FACE_Y)  # x, y
OPAQUE_GLASSES = engine.OPAQUE_GLASSES
BODIES = ("masculine", "feminine", "neutral")


def _cfg(**kw):
    base = {
        "hair": "bald",
        "hair_color": 1,
        "eyes": "dot",
        "brows": "none",
        "mouth": "smile",
        "outfit": "tshirt",
    }
    return engine.clean_config({**base, **kw})


def _layer_cells(rows, keys=None):
    return {
        (x, y): ch
        for y, line in rows.items()
        for x, ch in enumerate(line)
        if ch != "." and (keys is None or ch in keys)
    }


def _final(cfg):
    return {
        (x, y): ch
        for y, row in enumerate(engine.compose(cfg))
        for x, ch in enumerate(row)
        if ch != "."
    }


def _visible_fraction(cells, final):
    if not cells:
        return 1.0
    return sum(1 for pos, ch in cells.items() if final.get(pos) == ch) / len(cells)


def eyes_visible():
    """Los ojos deben verse con cualquier peinado y gorro, y con cualquier lente que no los tape a propósito."""
    problems = []
    for eyes, art in engine.EYES.items():
        cells = _layer_cells(art, keys="EeWw")
        for hair in engine.HAIR:
            for hat in engine.HEADWEAR:
                final = _final(_cfg(eyes=eyes, hair=hair, headwear=hat))
                frac = _visible_fraction(cells, final)
                if frac < 0.8:
                    problems.append(
                        f"ojos «{eyes}» tapados ({frac:.0%} visibles) por pelo «{hair}» + gorro «{hat}»"
                    )
        for glasses in engine.GLASSES:
            if glasses in OPAQUE_GLASSES:
                continue
            frac = _visible_fraction(cells, _final(_cfg(eyes=eyes, glasses=glasses)))
            if frac < 0.6:
                problems.append(f"lentes «{glasses}» tapan los ojos «{eyes}» ({frac:.0%} visibles)")
    return problems


def mouth_visible():
    problems = []
    for mouth, art in engine.MOUTHS.items():
        cells = _layer_cells(art)
        for facial in engine.FACIAL_HAIR:
            for hair in engine.HAIR:
                final = _final(_cfg(mouth=mouth, facial_hair=facial, hair=hair))
                frac = _visible_fraction(cells, final)
                if frac < 1.0:
                    problems.append(
                        f"boca «{mouth}» tapada ({frac:.0%}) por barba «{facial}» + pelo «{hair}»"
                    )
        for glasses in engine.GLASSES:
            for hat in engine.HEADWEAR:
                frac = _visible_fraction(
                    cells, _final(_cfg(mouth=mouth, glasses=glasses, headwear=hat))
                )
                if frac < 1.0:
                    problems.append(
                        f"boca «{mouth}» tapada ({frac:.0%}) por lentes «{glasses}» + gorro «{hat}»"
                    )
    return problems


def hats_clear_the_face():
    """Un gorro no puede dibujar nada sobre la cara (ojos, nariz, boca)."""
    problems = []
    xs, ys = FACE_WINDOW
    for hat, art in engine.HEADWEAR.items():
        for layer in ("back", "front"):
            bad = [(x, y) for (x, y) in _layer_cells(art[layer]) if x in xs and y in ys]
            if bad:
                problems.append(f"gorro «{hat}» ({layer}) dibuja sobre la cara en {bad[:3]}")
    return problems


def hair_clears_the_face():
    problems = []
    xs, ys = FACE_WINDOW
    for hair, art in engine.HAIR.items():
        bad = [(x, y) for (x, y) in _layer_cells(art["front"]) if x in xs and y in ys]
        if bad:
            problems.append(f"peinado «{hair}» (frente) dibuja sobre la cara en {bad[:3]}")
    return problems


def facial_hair_clears_the_eyes():
    problems = []
    for facial, art in engine.FACIAL_HAIR.items():
        bad = [(x, y) for (x, y) in _layer_cells(art) if y < 13 and 11 <= x <= 20]
        if bad:
            problems.append(f"barba «{facial}» llega a los ojos en {bad[:3]}")
    return problems


def detached_pixels():
    """Píxeles sueltos (no conectados al cuerpo) al combinar peinado y gorro: se ven como errores."""
    problems = []
    for hair in engine.HAIR:
        for hat in engine.HEADWEAR:
            final = _final(_cfg(hair=hair, headwear=hat))
            orphans = _orphans(final)
            if len(orphans) > 2:
                problems.append(
                    f"peinado «{hair}» + gorro «{hat}»: {len(orphans)} píxeles sueltos, p. ej. {sorted(orphans)[:3]}"
                )
    return problems


def _orphans(cells):
    """Celdas que no se conectan (8 vecinos) con el cuerpo principal."""
    if not cells:
        return set()
    seen, best = set(), set()
    for start in cells:
        if start in seen:
            continue
        stack, comp = [start], set()
        while stack:
            x, y = stack.pop()
            if (x, y) in comp or (x, y) not in cells:
                continue
            comp.add((x, y))
            stack.extend((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
        seen |= comp
        if len(comp) > len(best):
            best = comp
    return set(cells) - best


def hair_does_not_poke_above_the_hat():
    """Con gorro, el pelo no debe asomar por encima de la copa (el motor lo recorta; esto lo comprueba)."""
    problems = []
    for hat, art in engine.HEADWEAR.items():
        if hat == "none":
            continue
        cells = _layer_cells(art["front"])
        if not cells:
            continue
        top = min(y for _x, y in cells)
        for hair in engine.HAIR:
            final = _final(_cfg(hair=hair, headwear=hat, hair_color=0))
            hair_keys = {"H", "h", "j"}
            above = [(x, y) for (x, y), ch in final.items() if y < top and ch in hair_keys]
            if above:
                problems.append(f"peinado «{hair}» asoma sobre el gorro «{hat}» en {above[:3]}")
    return problems


def outfits_fit_every_body():
    problems = []
    for body in BODIES:
        for outfit in engine.OUTFITS:
            cfg = _cfg(body=body, outfit=outfit)
            final = _final(cfg)
            torso_cells = [
                (x, y) for (x, y), ch in final.items() if 20 <= y <= 27 and ch in "OoAaWKYRCNZ"
            ]
            if len(torso_cells) < 100:
                problems.append(f"ropa «{outfit}» casi no se ve en el cuerpo «{body}»")
    return problems


def neckwear_stays_on_the_body():
    problems = []
    for neck in engine.NECKWEAR:
        for outfit in engine.OUTFITS:
            final = _final(_cfg(neckwear=neck, outfit=outfit))
            for x, y in final:
                if not (0 <= x < GRID and 0 <= y < GRID):
                    problems.append(f"cuello «{neck}» sale de la grilla")
    return problems


CHECKS = [
    eyes_visible,
    mouth_visible,
    hats_clear_the_face,
    hair_clears_the_face,
    facial_hair_clears_the_eyes,
    detached_pixels,
    hair_does_not_poke_above_the_hat,
    outfits_fit_every_body,
    neckwear_stays_on_the_body,
]


def run_all():
    problems = []
    for check in CHECKS:
        problems += [f"[{check.__name__}] {p}" for p in check()]
    return problems


# `face` se importa para que un cambio de contrato de ojos/boca se note aquí.
_ = face
