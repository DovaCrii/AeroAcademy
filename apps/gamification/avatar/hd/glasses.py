"""Lentes HD (HD-3): ocho estilos a 2× la resolución de la cara. Coordenadas de la figura de 64: los ojos quedan en
x 23..27 y 36..40 (y 21..26); cada lente rodea un ojo y se dibuja con `mirror` (mitad izquierda + su espejo).

Los lentes transparentes se pintan DEBAJO de los ojos (el motor lo hace igual que en 32), así el ojo se ve dentro del aro;
los opacos (`sunglasses`, `goggles`, `fpv`) van encima y tapan los ojos a propósito. Claves: `F` marco (color elegido),
`L` cristal, `g` brillo, `K` contorno, `E`/`W` ojos pintados dentro de las gafas de piloto, `C` pantalla del visor.
"""

from . import HD, mirror, sprite

# Aros finos y redondos de 7×8 alrededor del ojo, patillas hacia las orejas y puente de una celda.
ROUND = mirror(
    20,
    20,
    [
        "....FFF..",
        "...F...F.",
        "FFF.....F",
        "..F.....F",
        "..F.....F",
        "..F.....F",
        "...F...F.",
        "....FFF..",
    ],
    bridge={3: "F"},
)

# Marco rectangular de una pieza.
SQUARE = mirror(
    20,
    20,
    [
        "..FFFFFFF",
        "..F.....F",
        "FFF.....F",
        "..F.....F",
        "..F.....F",
        "..F.....F",
        "..F.....F",
        "..FFFFFFF",
    ],
    bridge={3: "F"},
)

# Lentes grandes en gota, con brillo y doble puente.
AVIATOR = mirror(
    20,
    19,
    [
        "..FFFFFFFF",
        ".F.gg....F",
        ".F.......F",
        ".F.......F",
        ".F.......F",
        ".F.......F",
        "..F.....F.",
        "...F...F..",
        "....FFF...",
    ],
    bridge={2: "F", 4: "F"},
)

# Gafas de seguridad: marco con tapa superior gruesa y protección lateral.
SAFETY = mirror(
    18,
    19,
    [
        "...FFFFFFFF",
        "FFFFFFFFFFF",
        "FF..F.....F",
        "FF..F.....F",
        ".F..F.....F",
        "....F.....F",
        "....F.....F",
        "....FFFFFFF",
    ],
    bridge={1: "F", 4: "F"},
)

# Lentes de sol: cristal oscuro (F) con contorno y un brillo.
SUNGLASSES = mirror(
    20,
    19,
    [
        "..KKKKKKK",
        "..KFFFFFK",
        "..KgFFFFK",
        "KKKFgFFFK",
        "..KFFFFFK",
        "..KFFFFFK",
        "..KFFFFFK",
        "...KFFFK.",
        "....KKK..",
    ],
    bridge={3: "K"},
)

# Gafas de piloto: lente grande de cristal con los ojos pintados dentro y correa a los lados.
GOGGLES = mirror(
    14,
    19,
    [
        "......FFFFFFFFF",
        "......FLLLLLLLF",
        "......FLLLEEELF",
        "FFFFFFFLLEEEEEF",
        "FFFFFFFLLEWEEEF",
        "FFFFFFFLLEEEEEF",
        "......FLLEEEEEF",
        "......FLLLEEELF",
        "......FLLLLLLLF",
        "......FFFFFFFFF",
    ],
    bridge={3: "F", 4: "F"},
)

# Monóculo en el ojo derecho, con su cadenita.
MONOCLE = sprite(
    (35, 20),
    [
        "..FFF..",
        ".F...F.",
        "F.....F",
        "F.....F",
        "F.....F",
        "F.....F",
        ".F...F.",
        "..FFF..",
        "....F..",
        ".....F.",
    ],
)

# Visor FPV de piloto de dron: banda opaca con franja cian y correa; tapa los dos ojos.
_FILL, _BAND = "F" * 30, "FF" + "C" * 26 + "FF"
FPV = sprite(
    (12, 20),
    [
        "." * 4 + "K" * 32 + "." * 4,
        "." * 4 + "K" + _FILL + "K" + "." * 4,
        "K" * 5 + _BAND + "K" * 5,
        "K" + "FFF" + "K" + _BAND + "K" + "FFF" + "K",
        "K" * 5 + _FILL + "K" * 5,
        "." * 4 + "K" + _FILL + "K" + "." * 4,
        "." * 4 + "K" * 32 + "." * 4,
    ],
)

HD["glasses"].update(
    {
        "round": ROUND,
        "square": SQUARE,
        "aviator": AVIATOR,
        "safety": SAFETY,
        "sunglasses": SUNGLASSES,
        "goggles": GOGGLES,
        "monocle": MONOCLE,
        "fpv": FPV,
    }
)
