"""Gorros y sombreros. Contrato:

HEADWEAR = {id: {"back": rows, "front": rows}}  con rows = {y: fila de 32 caracteres}
  · "back"  detrás del cuerpo (ala trasera, audífonos por detrás); casi siempre vacío.
  · "front" SOBRE todo lo demás, incluido el pelo. Zona: y 0..13 (las copas de unos audífonos bajan hasta y 13).
No debe tapar los ojos (y 10..11). El pelo asoma por debajo según el peinado elegido.
Claves de color permitidas: K (contorno), T (principal), t (sombra), U (acento), W, Y, R, C, N, Z.
LABELS = {id: nombre en español}.

IDs obligatorios: none, cap (gorra), beanie (gorro de lana), hardhat (casco de obra), explorer (sombrero de explorador),
propeller (gorro con hélice de dron), headphones (audífonos), headband (cinta), beret (boina), bucket (sombrero de pescador).
"""

from ..art import full, sym

LABELS = {
    "none": "Sin gorro",
    "cap": "Gorra",
    "beanie": "Gorro de lana",
    "hardhat": "Casco de obra",
    "explorer": "Sombrero de explorador",
    "propeller": "Gorro con hélice",
    "headphones": "Audífonos",
    "headband": "Cinta",
    "beret": "Boina",
    "bucket": "Sombrero de pescador",
}


def _r(x: int, s: str) -> str:
    """Fila completa con el texto `s` colocado desde la columna x (para piezas asimétricas)."""
    return full("." * x + s + "." * (32 - x - len(s)))


HEADWEAR = {
    "none": {"back": {}, "front": {}},
    # Gorra de béisbol: cúpula, costura y visera hacia adelante.
    "cap": {
        "back": {},
        "front": {
            2: sym("..........KKKKKK"),
            3: sym(".........KTTTTTT"),
            4: sym("........KTTTTTTT"),
            5: sym("........KTTTTTTT"),
            6: sym(".......KKKKKKKKK"),
            7: sym("......KttttttttT"),
            8: sym("......KKKttttttt"),
            9: sym("........KKKKKKKK"),
        },
    },
    # Gorro de lana con pompón y puño tejido.
    "beanie": {
        "back": {},
        "front": {
            0: sym("............KUUU"),
            1: sym("...........KUUUU"),
            2: sym("..........KKTTTT"),
            3: sym("........KKTTTTTT"),
            4: sym("........KTTTTTTT"),
            5: sym("......KKKKKKKKKK"),
            6: sym("......KUtUtUtUtU"),
            7: sym("......KUtUtUtUtU"),
            8: sym("......KKKKKKKKKK"),
        },
    },
    # Casco de obra: cúpula con cresta y visera corta.
    "hardhat": {
        "back": {},
        "front": {
            1: sym("..............KK"),
            2: sym("...........KKKTT"),
            3: sym("........KKTTTtTT"),
            4: sym("........KTTTTtTT"),
            5: sym("........KTTTTtTT"),
            6: sym(".......KTTTTTtTT"),
            7: sym("......KKTTTTTTTT"),
            8: sym("......KKKKKKKKKK"),
        },
    },
    # Sombrero de explorador: copa con abolladura, cinta y ala ancha.
    "explorer": {
        "back": {},
        "front": {
            2: sym("..........KKKKKK"),
            3: sym(".........KTTTTTt"),
            4: sym(".........KTTTTtT"),
            5: sym(".........KTTTTTT"),
            6: sym(".........KUUUUUU"),
            7: sym("....KKKKKTTTTTTT"),
            8: sym("....KKttttttttTT"),
            9: sym("......KKKKKKKKKK"),
        },
    },
    # Gorro con hélice de dron.
    "propeller": {
        "back": {},
        "front": {
            0: sym(".........RRRKK.."),
            1: sym("........KRRRRRZZ"),
            2: sym("..............KZ"),
            3: sym("..........KKTTTT"),
            4: sym("........KKTTTUUU"),
            5: sym("........KTTTTUUU"),
            6: sym("........KTTTTUUU"),
            7: sym(".......KKKKKKKKK"),
        },
    },
    # Audífonos: arco sobre la cabeza y copas sobre las orejas.
    "headphones": {
        "back": {},
        "front": {
            2: sym("...........KKKKK"),
            3: sym(".........KKTTTTT"),
            4: sym("........KTK....."),
            5: sym("........KTK....."),
            6: sym("........KTK....."),
            7: sym("........KTK....."),
            8: sym("........KTK....."),
            9: sym(".....KKKKKK....."),
            10: sym("....KUUUUUK....."),
            11: sym("....KUUUUUK....."),
            12: sym("....KUUUUUK....."),
            13: sym(".....KKKKK......"),
        },
    },
    # Cinta de deportista con nudo y colas al costado derecho.
    "headband": {
        "back": {},
        "front": {
            6: sym("........KKKKKKKK"),
            7: sym("........KTTTTTTT"),
            8: sym("........KttttttT"),
            9: sym("........KKKKKKKK"),
        },
    },
    # Boina inclinada hacia la derecha con rabito.
    "beret": {
        "back": {},
        "front": {
            1: _r(20, "KUK"),
            2: _r(12, "KKKKKKKUKK"),
            3: _r(10, "KKTTTTTTTTTTKK"),
            4: _r(8, "KTTTTTTTTTTTTTTK"),
            5: _r(8, "KTTTTTTTTTTTTTTTK"),
            6: _r(9, "KtttTTTTTTTTTTTK"),
            7: _r(9, "KKKttttttttttKK"),
            8: _r(11, "KKKKKKKKK"),
        },
    },
    # Sombrero de pescador: copa baja y ala caída.
    "bucket": {
        "back": {},
        "front": {
            2: sym("..........KKKKKK"),
            3: sym(".........KTTTTTT"),
            4: sym("........KTTTTTTT"),
            5: sym("........KTTTTTTT"),
            6: sym("........KUUUUUUU"),
            7: sym("......KKKTTTTTTT"),
            8: sym("....KKKttttttttt"),
            9: sym(".....KKKKKKKKKKK"),
        },
    },
}
