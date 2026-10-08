"""Cuerpo base: cabeza, orejas, cuello, torso, brazos y piernas. Es el ancla de todas las demás piezas.

Mapa de coordenadas (x de 0 a 31, y de 0 a 31):
  cabeza (piel)        x 10..21 · y 5..16   contorno x 9..22 · y 4..17   orejas x 7..8 y 23..24 · y 10..12
  cuello               x 14..17 · y 18..19
  hombros / torso      x 6..25 (hombros y 20) · torso x 8..23 · y 20..27   brazos x 5..6 y 25..26 · y 21..26
  manos                x 5..6 y 25..26 · y 26
  cadera               y 28 · piernas y 29..30 · botas y 31
  centro de la cara    entre x 15 y x 16 (la grilla se espeja ahí)
"""

from ..art import sym

LABELS_BODY = {"masculine": "Hombre", "feminine": "Mujer", "neutral": "Neutro"}
LABELS_LEGWEAR = {"pants": "Pantalón", "shorts": "Short", "skirt": "Falda"}

# Silueta común. 'O' marca dónde va la ropa; las piezas de ropa solo decoran esas celdas.
BASE = {
    4: sym("...........KKKKK"),
    5: sym("..........KSSSSS"),
    6: sym(".........KSSSSSS"),
    7: sym(".........KSSSSSS"),
    8: sym(".........KSSSSSS"),
    9: sym(".........KSSSSSS"),
    10: sym(".......KSSSSSSSS"),
    11: sym(".......KSSSSSSSS"),
    12: sym(".......KSSSSSSSS"),
    13: sym(".........KSSSSSS"),
    14: sym(".........KSSSSSS"),
    15: sym(".........KSSSSSS"),
    16: sym("..........KSSSSS"),
    17: sym("...........KKKKK"),
    18: sym(".............Kss"),
    19: sym(".............KSS"),
    20: sym(".....KOOOOOOOOOO"),
    21: sym("....KOOKOOOOOOOO"),
    22: sym("....KOOKOOOOOOOO"),
    23: sym("....KOOKOOOOOOOO"),
    24: sym("....KOOKOOOOOOOO"),
    25: sym("....KOOKOOOOOOOO"),
    26: sym("....KSSKOOOOOOOO"),
    27: sym("....KKKKOOOOOOOO"),
    28: sym(".......KPPPPPPPP"),
    29: sym(".........KPPPPPK"),
    30: sym(".........KPPPPPK"),
    31: sym("........KBBBBBBK"),
}

# Nariz fija, un píxel de sombra a cada lado del centro.
NOSE = {12: sym("...............s")}

# Variantes de cuerpo: cambian hombros y mentón (la cara y la ropa siguen igual).
BODY_PATCH = {
    "masculine": {  # mentón cuadrado, cuello ancho y hombros anchos
        16: sym(".........KSSSSSS"),
        17: sym("..........KKKKKK"),
        18: sym("............Ksss"),
        19: sym("............KSSS"),
    },
    "feminine": {  # hombros angostos, cuello fino, cintura marcada y caderas anchas
        20: sym("......KOOOOOOOOO"),
        24: sym("....KOOKKOOOOOOO"),
        25: sym("....KOOKKOOOOOOO"),
        26: sym("....KSSKKOOOOOOO"),
        28: sym("......KPPPPPPPPP"),
    },
    "neutral": {  # hombros medios, mentón redondeado
        20: sym("......KOOOOOOOOO"),
    },
}

# Variantes de la parte baja.
LEGWEAR = {
    "pants": {},
    "shorts": {
        30: sym(".........KSSSSSK"),
    },
    "skirt": {
        28: sym("......KPPPPPPPPP"),
        29: sym(".....KPPPPPPPPPP"),
        30: sym(".........KSSSSSK"),
    },
}
