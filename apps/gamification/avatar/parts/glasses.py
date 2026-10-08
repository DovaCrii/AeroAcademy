"""Lentes. Contrato:

GLASSES = {id: rows}  con rows = {y: fila de 32 caracteres}; se pintan SOBRE los ojos. Zona: y 8..13.
Los ojos quedan a x 12..13 y 18..19: el lente de cada ojo cubre unos x 11..14 y 17..20, con un puente en x 15..16.
Claves de color permitidas: F (marco), L (cristal, claro), g (brillo), K (contorno), E (ojo oscuro: el lente puede dejar ver el ojo),
W (blanco). Los lentes de sol usan F como cristal oscuro.
LABELS = {id: nombre en español}.

IDs obligatorios: none, round, square, aviator, goggles (gafas de piloto), sunglasses, monocle.
"""

from ..art import mix, sym

LABELS = {
    "none": "Sin lentes",
    "round": "Redondos",
    "square": "Cuadrados",
    "aviator": "Aviador",
    "goggles": "Gafas de piloto",
    "sunglasses": "De sol",
    "monocle": "Monóculo",
}

_E = "." * 16

GLASSES = {
    "none": {},
    # Aros redondos finos; el ojo queda al descubierto dentro del aro.
    "round": {
        9: sym("............FF.."),
        10: sym(".........FFF..FF"),
        11: sym("...........F..F."),
        12: sym("............FF.."),
    },
    # Marco de una pieza, ancho y rectangular, con cristal claro a los lados del ojo.
    "square": {
        9: sym("..........FFFFFF"),
        10: sym("........FFFL..LF"),
        11: sym("..........FL..LF"),
        12: sym("..........FFFFFF"),
    },
    # Lentes grandes en gota con brillo y doble puente.
    "aviator": {
        9: sym("...........FFFF."),
        10: sym("..........Fg..LF"),
        11: sym("..........FL..LF"),
        12: sym("...........FLLF."),
        13: sym("............FF.."),
    },
    # Gafas de piloto: lente grande con cristal, ojos pintados dentro y correa a los lados.
    "goggles": {
        8: sym("...........FFFF."),
        9: sym("..........FLLLLF"),
        10: sym(".......FFFFgEELF"),
        11: sym(".......FFFFLEELF"),
        12: sym("..........FLLLLF"),
        13: sym("...........FFFF."),
    },
    # Lentes de sol: cristal oscuro (F) con brillo.
    "sunglasses": {
        9: sym("..........KKKKKK"),
        10: sym("........KKKgFFFK"),
        11: sym("..........KFFFFK"),
        12: sym("...........KKKK."),
    },
    # Monóculo en el ojo derecho (del avatar: x 18..19) con cadenita.
    "monocle": {
        8: mix(_E, "..FF............"),
        9: mix(_E, ".FLLF..........."),
        10: mix(_E, "FL..LF.........."),
        11: mix(_E, "FL..LF.........."),
        12: mix(_E, ".FLLFF.........."),
        13: mix(_E, "..FF..F........."),
    },
}
