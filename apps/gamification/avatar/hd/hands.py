"""Manos HD (HD-7): la mano que sujeta el equipo, la mano abierta de «Saluda» y el antebrazo de «Trabajando».

`GRIP` (4×4) es la mano derecha de las herramientas; la dibuja `parts.gear.Canvas.hand`. `POSE_HANDS` pinta la mano de
una pose sobre el brazo movido por la propia pose (coordenadas de la figura de 64). Claves: `K S s`.
"""

from . import sprite

GRIP = [".KK.", "KSSK", "KssK", ".KK."]

POSE_HANDS = {
    # Mano abierta junto a la cabeza: cuatro dedos y la palma.
    "wave": sprite(
        (6, 18),
        [
            "..K.K.K.",
            ".KSKSKSK",
            ".KSSSSSK",
            ".KSSSSsK",
            "..KSSSK.",
            "...KKK..",
        ],
    ),
}

# Piezas de pose que van **delante** del torso y de la ropa (se pintan después de ella y del accesorio de cuello).
# «Trabajando»: el antebrazo izquierdo cruza la cintura hacia el equipo de la derecha; manga (`O` y su sombra `o`) y una
# mano abierta que señala. Va por debajo del pecho (y 49..55), así no toca la cara ni el pin de nivel.
_WORK_HAND = [  # mano abierta que señala hacia la derecha (10×7)
    ".KKKKK....",
    "KSSSSSKKK.",
    "KSSSSSSSSK",
    "KSSSSSSSsK",
    "KSSSSSKKKK",
    "KsSSSsK...",
    ".KKKKK....",
]
_WORK_SLEEVE = ["." * 19, "K" * 19, "O" * 17 + "oo", "O" * 17 + "oo", "o" * 19, "K" * 19, "." * 19]
POSE_FRONT = {
    "work": sprite(
        (10, 49), [sleeve + hand for sleeve, hand in zip(_WORK_SLEEVE, _WORK_HAND, strict=True)]
    ),
}
