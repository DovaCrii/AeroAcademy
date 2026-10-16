"""Poses del avatar (solo vista previa del escenario HD; no se guardan en la configuración).

Una pose es un parche sobre el cuerpo base: `{y: (x, "caracteres")}` en coordenadas de la grilla de 32. A diferencia de
una pieza de ropa, el parche **reemplaza** las celdas, y un `.` las deja vacías: así un brazo se mueve de lugar. Se
aplica después del cuerpo y antes de la ropa, el cuello y todo lo demás.

Contrato para quien dibuje una pose:
  · solo toca los brazos (x 2..7 o 24..29, y 8..27); la cara y el torso no se tocan;
  · usa las claves del cuerpo: `K` contorno, `S` piel, `O` ropa;
  · el equipo de la mano derecha (carril x 23..31) no debe quedar cortado: las poses mueven el brazo izquierdo.
"""

LABELS_POSES = {"stand": "De pie", "wave": "Saluda"}

POSES = {
    "stand": {},
    "wave": {  # el brazo izquierdo sube y la mano queda junto a la cabeza
        10: (3, ".KK."),
        11: (3, "KSSK"),
        12: (3, "KSSK"),
        13: (3, "KOOK"),
        14: (3, "KOOK"),
        15: (3, "KOOK"),
        16: (3, "KOOK"),
        17: (3, "KOOK"),
        18: (3, "KOOK"),
        19: (3, "KOOK"),
        21: (4, "...K"),
        22: (4, "...K"),
        23: (4, "...K"),
        24: (4, "...K"),
        25: (4, "...K"),
        26: (4, "...K"),
        27: (4, "...K"),
    },
}
DEFAULT_POSE = "stand"
