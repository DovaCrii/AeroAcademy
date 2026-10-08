"""Peinados. Contrato:

HAIR = {id: {"back": rows, "front": rows}}  con rows = {y: fila de 32 caracteres}
  · "back"  se pinta DETRÁS del cuerpo (pelo largo que cae sobre los hombros, coleta, trenzas).
  · "front" se pinta SOBRE la cabeza (flequillo, volumen). Puede tapar la frente (y 5..8) pero no los ojos (y 10..11).
Claves de color permitidas: K (contorno), H (pelo), h (luz), j (sombra).
LABELS = {id: nombre en español}.

IDs obligatorios: bald, buzz, short, side_part, quiff, curly, afro, long, wavy, ponytail, bun, bob, braids, mohawk.

Mapa útil: cabeza x10..21 (contorno K x9..22), y5..16; orejas x7..8 / x23..24 en y10..12; ojos y10..11; cuello x14..17.

Ayudantes locales (solo para dibujar sin contar columnas):
  · `_s(x, texto)`: coloca `texto` desde la columna x en la mitad izquierda y la espeja (simétrico).
  · `_r(x, texto, ...)`: fila completa; cada par (x, texto) se superpone (asimétrico).
"""

from ..art import full

W = 32


def _r(*segs) -> str:
    """Fila de 32 con segmentos (x, texto) superpuestos; '.' no pisa."""
    row = ["."] * W
    it = iter(segs)
    for x, txt in zip(it, it, strict=True):
        for i, c in enumerate(txt):
            if c != ".":
                row[x + i] = c
    return full("".join(row))


def _s(x, txt, *extra) -> str:
    """Simétrico: `txt` se coloca desde x (izquierda) y se espeja a la derecha."""
    mirrored = txt[::-1]
    return _r(x, txt, W - x - len(txt), mirrored, *extra)


LABELS = {
    "bald": "Calvo",
    "buzz": "Rapado",
    "short": "Corto",
    "side_part": "Raya al costado",
    "quiff": "Jopo",
    "curly": "Rizado",
    "afro": "Afro",
    "long": "Largo",
    "wavy": "Ondulado",
    "ponytail": "Cola de caballo",
    "bun": "Moño",
    "bob": "Melena corta",
    "braids": "Trenzas",
    "mohawk": "Mohicano",
}

# Tapa base de la coronilla reutilizable (y3..y7), cuerpo del pelo ceñido a la cabeza.
_CAP = {
    3: _s(12, "KKKK"),
    4: _s(10, "KHHHHH"),
    5: _s(10, "KHHHhH"),
    6: _s(9, "KHHHHHHH"),
    7: _s(9, "KHHhHHHH"),
}

HAIR = {
    "bald": {"back": {}, "front": {}},
    # Rapado: casquete finísimo con textura de puntos.
    "buzz": {
        "back": {},
        "front": {
            4: _s(10, "KjHjHj"),
            5: _s(10, "HjHHjH"),
            6: _s(10, "HHjHHj"),
            7: _s(10, "jHHjHH"),
            8: _s(10, "Hj"),
        },
    },
    "short": {
        "back": {},
        "front": {
            **_CAP,
            8: _s(10, "HHj"),
        },
    },
    # Raya al costado: raya a la izquierda del espectador, mechón que cae hacia la derecha.
    "side_part": {
        "back": {},
        "front": {
            2: _r(11, "KKKKKKKK"),
            3: _r(9, "KHHHjHHHHHHHHK"),
            4: _r(9, "KHHHjHHhHHHHHHK"),
            5: _r(9, "KHHHjHHHHHHHHHHK"),
            6: _r(9, "KHHHjHHHHhHHHHHHK"),
            7: _r(9, "KHHHjHHHHHHHHHHHK"),
            8: _r(10, "HHj", 17, "HHHHH"),
            9: _r(10, "H", 19, "HHH"),
        },
    },
    # Jopo: copete alto peinado hacia atras y a un lado, laterales cortos.
    "quiff": {
        "back": {},
        "front": {
            0: _r(14, "KKKKKKK"),
            1: _r(12, "KKHHHhHHHK"),
            2: _r(10, "KKHHHHhHHHHHK"),
            3: _r(10, "KHHHhHHHHHHHK"),
            4: _r(10, "KHjHHhHHHHHK"),
            5: _r(10, "jHHjHHHHHHHj"),
            6: _r(10, "HHjHHhHHHjHH"),
            7: _r(10, "Hj", 20, "jH"),
            8: _r(10, "H", 21, "H"),
        },
    },  # Rizado: nube de rulos con silueta ondulada.
    "curly": {
        "back": {
            9: _s(5, "KHHK"),
            10: _s(5, "KHHK"),
            11: _s(5, "KHHK"),
            12: _s(6, "KHHK"),
            13: _s(7, "KKK"),
        },
        "front": {
            1: _s(11, "KKKKK"),
            2: _s(8, "KKHHhHHH"),
            3: _s(6, "KKHHHhHHHHH"),
            4: _s(5, "KHHhHHHHHHHH"),
            5: _s(5, "KHHHHjHHHhHH"),
            6: _s(5, "KHhHHHHjHHHH"),
            7: _s(5, "KHHHjHHHHhHH"),
            8: _s(5, "KHHHHhHHHj"),
            9: _s(6, "KHHHj"),
        },
    },
    # Afro: volumen enorme y redondo.
    "afro": {
        "back": {
            8: _s(2, "KHHHHHH"),
            9: _s(2, "KHHHHHHH"),
            10: _s(2, "KHHHHHHH"),
            11: _s(2, "KHHHHHHH"),
            12: _s(2, "KHHHHHHH"),
            13: _s(3, "KHHHHHH"),
            14: _s(4, "KHHHHj"),
            15: _s(6, "KKKK"),
        },
        "front": {
            0: _s(10, "KKKKKK"),
            1: _s(7, "KKKHHHHHH"),
            2: _s(5, "KKHHHhHHHHHH"),
            3: _s(4, "KHHHHHHhHHHHHH"),
            4: _s(3, "KHHhHHHHHHHHHHHH"),
            5: _s(3, "KHHHHHHjHHHhHHHH"),
            6: _s(2, "KHHhHHHHHHHHHHHHH"[:14]),
            7: _s(2, "KHHHHHHHHjHHHHHH"),
            8: _s(2, "KHHHHhHHHHHHHHHH"[:14]),
            9: _s(2, "KHHHHHHHHj"),
            10: _s(2, "KHHHHHH"),
        },
    },
    # Largo: melena lisa con raya al medio y mechones al frente.
    "long": {
        "back": {
            6: _s(8, "KHHHHHHH"),
            7: _s(7, "KHHHHHHHH"),
            **{y: _s(6, "KHHHHHHHHH") for y in range(8, 20)},
        },
        "front": {
            2: _s(14, "KK"),
            3: _s(11, "KKHHH"),
            4: _s(9, "KHHHHHHH"),
            5: _s(8, "KHHhHHHHH"),
            6: _s(8, "KHHHHHjHH"),
            7: _s(8, "KHHHHjHHH"),
            8: _s(8, "KHHHHhHj"),
            9: _s(8, "KHHHh"),
            10: _s(8, "KHHH"),
            11: _s(8, "KHHj"),
            12: _s(8, "KHHj"),
            13: _s(8, "KHHj"),
            14: _s(8, "KHHj"),
            15: _s(8, "KHHj"),
            16: _s(8, "KHHj"),
            17: _s(8, "KHHj"),
            18: _s(8, "KHHj"),
            19: _s(8, "KHHj"),
            20: _s(8, "KHHj"),
            21: _s(8, "KHHj"),
            22: _s(8, "KHHj"),
            23: _s(8, "KHHK"),
            24: _s(9, "KKK"),
        },
    },
    # Ondulado: a la altura del hombro, con ondas y puntas hacia afuera.
    "wavy": {
        "back": {
            6: _s(7, "KHHHHHHHH"),
            **{y: _s(5, "KHHHHHHHHHH") for y in range(7, 20)},
        },
        "front": {
            1: _s(12, "KKKK"),
            2: _s(9, "KKHHHhHH"),
            3: _s(8, "KHHHHHhHH"),
            4: _s(7, "KHHhHHHHHH"),
            5: _s(7, "KHHHHHjHHH"),
            6: _s(7, "KHhHHHHHjH"),
            7: _s(7, "KHHHjHHHHH"),
            8: _s(7, "KHHHHHhHj"),
            9: _s(7, "KHHHhj"),
            10: _s(6, "KHHHj"),
            11: _s(7, "KHHHj"),
            12: _s(6, "KHHHj"),
            13: _s(6, "KHHHj"),
            14: _s(7, "KHHHj"),
            15: _s(6, "KHHHj"),
            16: _s(6, "KHHHj"),
            17: _s(7, "KHHHj"),
            18: _s(6, "KHHHj"),
            19: _s(5, "KHHHHj"),
            20: _s(5, "KHHHHj"),
            21: _s(5, "KKHHK"),
            22: _s(6, "KKK"),
        },
    },
    # Cola de caballo: recogido alto, cola que cuelga al costado derecho.
    "ponytail": {
        "back": {
            3: _r(22, "KKK"),
            4: _r(22, "KHHK"),
            5: _r(23, "KHHHK"),
            6: _r(24, "KHHHK"),
            7: _r(25, "KHHHK"),
            8: _r(25, "KHHhK"),
            9: _r(26, "KHHHK"),
            10: _r(26, "KHHHK"),
            11: _r(26, "KHHjK"),
            12: _r(26, "KHHHK"),
            13: _r(26, "KHHjK"),
            14: _r(26, "KHjHK"),
            15: _r(27, "KHHK"),
            16: _r(27, "KjHK"),
            17: _r(27, "KHK"),
            18: _r(28, "KK"),
        },
        "front": {
            3: _s(12, "KKKK"),
            4: _s(10, "KHHHHH"),
            5: _s(10, "KHHhHH"),
            6: _s(9, "KHHHHHHH", 22, "KjK"),
            7: _s(9, "KHHhHHHH", 22, "jjK"),
            8: _s(10, "Hj"),
        },
    },
    # Moño: bola alta sobre la coronilla y pelo liso tirante.
    "bun": {
        "back": {},
        "front": {
            0: _s(12, "KKKK"),
            1: _s(11, "KHHHH"),
            2: _s(11, "KHhHH"),
            3: _s(11, "KHHjj"),
            4: _s(10, "KHjjjj"),
            5: _s(10, "KHHhHH"),
            6: _s(9, "KHHHHHHH"),
            7: _s(9, "KHHHHHHH"),
            8: _s(10, "HHj"),
        },
    },
    # Melena corta (bob): corte a la mandíbula, flequillo recto.
    "bob": {
        "back": {
            14: _s(5, "KHHHHHH"),
            15: _s(5, "KHHHHHH"),
            16: _s(5, "KHHHHHH"),
            17: _s(6, "KHHHHH"),
        },
        "front": {
            2: _s(12, "KKKK"),
            3: _s(9, "KKHHhHHH"),
            4: _s(8, "KHHHHHHHH"),
            5: _s(7, "KHHhHHHHHH"),
            6: _s(6, "KHHHHHHHHHH"),
            7: _s(6, "KHHHHhHHHHH"),
            8: _s(6, "KHHHHHHHHHHH"),
            9: _s(6, "KHHHjj"),
            10: _s(6, "KHHHj"),
            11: _s(6, "KHHHj"),
            12: _s(6, "KHHHj"),
            13: _s(6, "KHHHj"),
            14: _s(6, "KHHHHj"),
            15: _s(6, "KHHHHj"),
            16: _s(7, "KKKKK"),
        },
    },
    # Trenzas: dos trenzas sobre los hombros con raya al medio.
    "braids": {
        "back": {},
        "front": {
            3: _s(12, "KKKK"),
            4: _s(10, "KHHHHj"),
            5: _s(10, "KHHhHj"),
            6: _s(9, "KHHHHHHj"),
            7: _s(9, "KHHhHHHj"),
            8: _s(8, "KHHHH"),
            9: _s(8, "KHHj"),
            10: _s(7, "KHHHK"),
            11: _s(7, "KHhHK"),
            12: _s(7, "KHHHK"),
            13: _s(7, "KjHHK"),
            14: _s(7, "KHhHK"),
            15: _s(7, "KHHjK"),
            16: _s(7, "KHhHK"),
            17: _s(7, "KjHHK"),
            18: _s(7, "KHhHK"),
            19: _s(7, "KHHjK"),
            20: _s(7, "KHhHK"),
            21: _s(7, "KjHHK"),
            22: _s(7, "KHhHK"),
            23: _s(7, "KHHjK"),
            24: _s(7, "KjHHK"),
            25: _s(8, "KHjK"),
            26: _s(8, "KKKK"),
        },
    },
    # Mohicano: cresta alta al centro, costados rapados.
    "mohawk": {
        "back": {},
        "front": {
            0: _s(14, "KK"),
            1: _s(12, "KKHH"),
            2: _s(12, "KHHh"),
            3: _s(12, "KHHH"),
            4: _s(12, "KHhH"),
            5: _s(11, "jKHHH"),
            6: _s(10, "jjKHHH"),
            7: _s(10, "jjKHjH"),
            8: _s(11, "jjKj"),
        },
    },
}


def _off_face(rows):
    """Ningún peinado dibuja sobre la cara (x 11..20, y 10..16): se quitan los mechones que caen sobre ella."""
    out = {}
    for y, line in rows.items():
        if 10 <= y <= 16:
            line = "".join("." if 11 <= x <= 20 else ch for x, ch in enumerate(line))
        out[y] = line
    return out


for _style in HAIR.values():
    _style["front"] = _off_face(_style["front"])
