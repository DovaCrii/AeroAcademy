"""Manos HD (HD-7): la mano que sujeta el equipo y la mano abierta de la pose «Saluda».

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
