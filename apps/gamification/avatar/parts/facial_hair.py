"""Vello facial (barba, bigote). Contrato:

FACIAL_HAIR = {id: rows}  con rows = {y: fila de 32 caracteres}; se pinta SOBRE la cabeza, ANTES de la boca
(la boca se dibuja encima, así que puede quedar un hueco en y 14..15 o dejar que la boca lo cubra).
Zona: mejillas y mentón, x 10..21 · y 11..17 (la barba puede bajar hasta y 18 sobre el cuello).
Claves de color permitidas: H, h, j (color del pelo), K.
LABELS = {id: nombre en español}.

IDs obligatorios: none, stubble (barba de días), mustache, goatee (perilla), beard, full_beard.
"""

from ..art import sym

LABELS = {
    "none": "Sin barba",
    "stubble": "Barba de días",
    "mustache": "Bigote",
    "goatee": "Perilla",
    "beard": "Barba",
    "full_beard": "Barba completa",
}

FACIAL_HAIR = {
    "none": {},
    "stubble": {
        13: sym("..........j.j.j."),
        14: sym("...........j.j.."),
        15: sym("..........j.j..."),
        16: sym("...........j.j.j"),
    },
    "mustache": {
        13: sym("............HHHH"),
        14: sym("............H..."),
    },
    "goatee": {
        16: sym("............HHHH"),
        17: sym("..............HH"),
    },
    "beard": {
        13: sym("..........HHHHHH"),
        14: sym("..........HHH..."),
        15: sym("..........HHH..."),
        16: sym("..........HHHHHH"),
        17: sym("...........HHHHH"),
    },
    "full_beard": {
        10: sym("..........H....."),
        11: sym("..........H....."),
        12: sym("..........H....."),
        13: sym("..........HHHHHH"),
        14: sym("..........HHHjH."),
        15: sym("..........HHHhH."),
        16: sym("..........HHHHHH"),
        17: sym("..........HHHHHH"),
        18: sym("............HHHH"),
    },
}

LABELS.update({"sideburns": "Patillas", "handlebar": "Bigote manubrio"})

FACIAL_HAIR["sideburns"] = {y: sym("..........H.....") for y in range(10, 15)}
FACIAL_HAIR["handlebar"] = {
    13: sym("...........HHHHH"),
    14: sym("...........H...."),
}
