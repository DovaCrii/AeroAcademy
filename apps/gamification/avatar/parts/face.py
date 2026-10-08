"""Cara: ojos, cejas y boca. Contrato:

EYES, BROWS, MOUTHS = {id: rows}  con rows = {y: fila de 32 caracteres}; se pintan SOBRE la cabeza.
Zona de la cara (piel): x 10..21 · y 5..16. Ojos: y 10..11 (hasta y 12 si son grandes), centrados en x 12..13 y 18..19.
Cejas: y 8..9. Boca: y 14..15 (y 16 si es abierta). La nariz ya está dibujada en y 12 (x 15 y 16): no la tapes.
Claves de color permitidas:
  EYES   → K, E (ojo oscuro), e (iris), W (blanco/brillo)
  BROWS  → H, h, j (color del pelo), K
  MOUTHS → K, M (interior), m (labios), W (dientes)
LABELS_EYES / LABELS_BROWS / LABELS_MOUTHS = {id: nombre en español}.

IDs obligatorios:
  EYES   dot, iris, happy, lashes, wink
  BROWS  normal, thick, thin, none, raised
  MOUTHS smile, neutral, grin, open, smirk, surprised
"""

from ..art import mix, sym

LABELS_EYES = {
    "dot": "Puntos",
    "iris": "Con iris",
    "happy": "Felices",
    "lashes": "Pestañas",
    "wink": "Guiño",
}
LABELS_BROWS = {
    "none": "Sin cejas",
    "normal": "Normales",
    "thick": "Gruesas",
    "thin": "Finas",
    "raised": "Levantadas",
}
LABELS_MOUTHS = {
    "smile": "Sonrisa",
    "neutral": "Neutra",
    "grin": "Sonrisa grande",
    "open": "Abierta",
    "smirk": "Sonrisa de lado",
    "surprised": "Sorprendida",
}

EYES = {
    # 2x2 oscuros con un píxel de brillo arriba a la izquierda
    "dot": {
        11: mix("............WE..", "..WE............"),
        12: sym("............EE.."),
    },
    # 3x3 con blanco, iris (color elegido) y pupila
    "iris": {
        11: sym("...........EEE.."),
        12: sym("...........WeE.."),
        13: sym("...........WeW.."),
    },
    # arcos ^ ^
    "happy": {
        11: sym("............EE.."),
        12: sym("...........E..E."),
    },
    # ojo con pestañas marcadas: párpado grueso y flick hacia afuera
    "lashes": {
        10: sym("..........E....."),
        11: sym("...........EEE.."),
        12: sym("...........WeE.."),
    },
    # ojo izquierdo abierto, derecho cerrado en arco
    "wink": {
        11: mix("............WE..", "..EE............"),
        12: mix("............EE..", ".E..E..........."),
    },
}

BROWS = {
    "none": {},
    "normal": {9: sym("...........HHHH.")},
    "thick": {8: sym("...........HHHH."), 9: sym("..........HHHHH.")},
    "thin": {9: sym("...........jjj..")},
    "raised": {8: sym("............HHH."), 9: sym("...........H....")},
}

MOUTHS = {
    "smile": {14: sym(".............K.."), 15: sym("..............KK")},
    "neutral": {15: sym(".............KKK")},
    "grin": {
        14: sym("............KWWW"),
        15: sym(".............KKK"),
    },
    "open": {
        14: sym(".............KKK"),
        15: sym(".............KMM"),
        16: sym("..............KK"),
    },
    "smirk": {
        14: mix("................", "..K............."),
        15: mix(".............KKK", "KK.............."),
    },
    "surprised": {
        14: sym("...............K"),
        15: sym("..............KM"),
        16: sym("...............K"),
    },
}
