"""Vello facial HD (HD-3): siete estilos con textura de dos tonos, a la resolución de la figura de 64.

Zona: mejillas, bigote y mentón, x 18..45 · y 20..39. Se pinta SOBRE la cabeza y ANTES de la boca (la boca queda encima,
así que la barba puede pasar por detrás de ella). Cada pieza es un par simétrico (`mirror`): se dibuja la mitad izquierda.
Claves: `H` pelo, `h` luz, `j` sombra.
"""

from . import HD, mirror

# Sombra de unos días: puntos sueltos en mejillas y mentón.
STUBBLE = mirror(
    21,
    26,
    [
        "j...j...j..",
        "..j...j...j",
        "....j...j.j",
        ".j...j...j.",
        "...j...j...",
        ".j...j...j.",
        "..j...j...j",
        "....j...j..",
    ],
)

# Bigote tupido sobre la boca, con las puntas hacia abajo.
MUSTACHE = mirror(
    26,
    26,
    [
        "..hHHH",
        ".HHHHH",
        "HHHjjj",
        "HH....",
    ],
)

# Perilla: tapa el mentón y baja un poco sobre el cuello.
GOATEE = mirror(
    26,
    32,
    [
        "..HHHH",
        ".HHHHH",
        ".HHHjj",
        "..HHjj",
    ],
)

# Barba: patillas, mejillas y mentón con un hueco alrededor de la boca.
BEARD = mirror(
    20,
    26,
    [
        "HHH.........",
        "HHHHH.......",
        "HHHHHH......",
        "HHHHHH......",
        "HHHHHH......",
        "HHHHHHH.....",
        "HHHHHHHHHHHH",
        "HHHHHHHHHHHH",
        ".HHHHHHHHHjj",
        "..HhHHHHHjjj",
    ],
)

# Barba completa: patillas hasta la sien, bigote y barba juntos, con luz y sombra.
FULL_BEARD = mirror(
    20,
    20,
    [
        "HH..........",
        "HH..........",
        "HH..........",
        "HH..........",
        "HHH.........",
        "HHHH........",
        "HHHHHhHHHHHH",
        "HHHHHHHHHHHj",
        "HHHHHHHHHHjj",
        "HHHHHHHHHHjj",
        "HHHHhHHHHHjj",
        "HHHHHHHHHHjj",
        "HHHHHHHHHHHH",
        "HHHHHHHHHHHH",
        ".HHHHHHHHjjj",
        "..HHhHHHHjjj",
        "...HHHHHHjjj",
        "....HHHHHHHH",
    ],
)

# Patillas largas: una tira a cada lado hasta la mandíbula.
SIDEBURNS = mirror(
    20,
    20,
    [
        "HH",
        "HH",
        "HH",
        "HH",
        "HH",
        "HH",
        "HH",
        "HH",
        "Hj",
        ".j",
    ],
)

# Bigote manubrio: las puntas se enroscan hacia arriba.
HANDLEBAR = mirror(
    22,
    25,
    [
        "H.........",
        "HH..hHHHHH",
        ".HHHHHHHHH",
        "..HHjjHHHj",
    ],
)

HD["facial_hair"].update(
    {
        "stubble": STUBBLE,
        "mustache": MUSTACHE,
        "goatee": GOATEE,
        "beard": BEARD,
        "full_beard": FULL_BEARD,
        "sideburns": SIDEBURNS,
        "handlebar": HANDLEBAR,
    }
)
