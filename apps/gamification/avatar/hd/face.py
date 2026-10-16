"""Cara HD (HD-2): ojos, cejas, boca y nariz dibujados a la resolución de la figura de 64×64.

Coordenadas de la figura de 64 (la ventana de la cara de 32 ×2): ojos en x 22..41 e y 20..27, cejas en y 14..19, nariz en
x 30..33 · y 24..25, boca en x 26..37 · y 28..33. Cada pieza es un sprite con ancla: un ojo mide 5×6 celdas (el de 32
medía 2×2), una ceja 6×2, una boca hasta 10×4.

Claves: ojos `K E e W`, cejas `H h j`, boca `K M m W`, nariz `s`; nunca `1..5` (las pone el motor).
Los ojos y las cejas se dibujan como un par: la mitad izquierda son 8 columnas, 4 de hueco en el centro (la nariz) y el
espejo de la izquierda a la derecha (o una mitad derecha propia si el par no es simétrico, como el guiño).
"""

from . import HD, sprite

GAP = "...."  # entre los dos ojos: x 30..33


def _pair(top, left, right=None, x=22):
    """Un par de ojos o de cejas. `left` son filas de 8 caracteres; `right` es su espejo si no se da."""
    assert all(len(row) == 8 for row in left), left
    right = right or [row[::-1] for row in left]
    assert len(right) == len(left) and all(len(row) == 8 for row in right), right
    return sprite((x, top), [a + GAP + b for a, b in zip(left, right, strict=True)])


# --- ojos: y 20..27 -------------------------------------------------------------------------------------------------

_DOT = [
    "..EEE...",
    ".EEEEE..",
    ".EWEEE..",
    ".EEEEE..",
    ".EEEEE..",
    "..EEE...",
]
EYES = {
    # ojos redondos oscuros con un brillo hacia afuera
    "dot": _pair(21, _DOT),
    # blanco, iris del color elegido y pupila, con un párpado de contorno
    "iris": _pair(
        21,
        [
            "..KKK...",
            ".KWWWK..",
            ".WWeeW..",
            ".WeEeW..",
            ".WeeeW..",
            ".KWWWK..",
            "..KKK...",
        ],
    ),
    # arcos felices ^ ^
    "happy": _pair(
        22,
        [
            "..EEE...",
            ".EE.EE..",
            ".E...E..",
        ],
    ),
    # párpado grueso con flick hacia afuera y pestañas
    "lashes": _pair(
        20,
        [
            "E.......",
            ".EEEEE..",
            ".WeeeW..",
            ".WeEeW..",
            ".WeeeW..",
            "..WWW...",
        ],
    ),
    # izquierdo abierto, derecho cerrado en arco
    "wink": _pair(
        21,
        _DOT,
        [
            "........",
            "........",
            "..E...E.",
            "...EEE..",
            "........",
            "........",
        ],
    ),
}

# --- cejas: y 14..19 ------------------------------------------------------------------------------------------------

BROWS = {
    "normal": _pair(16, ["..hHHH..", ".HHHHHH.", ".HHHHHH."]),
    "thick": _pair(15, ["..hHHHH.", ".HHHHHHH", ".HHHHHHH", ".HHHHHH."]),
    "thin": _pair(17, [".HHHHHH.", "..HHHH.."]),
    "raised": _pair(14, ["..hHHH..", ".HHHHHH.", ".HH..HH.", ".H....H."]),
}

# --- boca: x 26..37 · y 28..33 --------------------------------------------------------------------------------------

MOUTHS = {
    "smile": sprite((27, 29), ["K........K", ".KmmmmmmK.", "..KKKKKK.."]),
    "neutral": sprite((27, 30), [".KKKKKKKK.", "..mmmmmm.."]),
    "grin": sprite((27, 29), ["K........K", "KWWWWWWWWK", ".KWWWWWWK.", "..KKKKKK.."]),
    "open": sprite((27, 29), [".KKKKKKKK.", "KMMMMMMMMK", ".KMMMMMMK.", "..KKKKKK.."]),
    "smirk": sprite((27, 29), ["........KK", ".KKKKKKK..", "..mmmmm..."]),
    "surprised": sprite((29, 29), [".KKKK.", "KMMMMK", "KMMMMK", ".KKKK."]),
}

# --- nariz: x 30..33 · y 24..25 (una sola, no es una opción del catálogo) --------------------------------------------

NOSE = {"default": sprite((30, 24), [".ss.", "ssss"])}

HD["eyes"].update(EYES)
HD["brows"].update(BROWS)
HD["mouth"].update(MOUTHS)
HD["nose"].update(NOSE)
