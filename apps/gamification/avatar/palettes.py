"""Paletas del avatar: lo que la persona puede elegir. Cada entrada tiene un nombre en español."""

SKINS = [
    ("Muy clara", {"S": "#FBDDC4", "s": "#E9B795"}),
    ("Clara", {"S": "#F2C9A0", "s": "#D9A577"}),
    ("Media clara", {"S": "#E0A87A", "s": "#C28A5C"}),
    ("Trigueña", {"S": "#C68642", "s": "#A66A2E"}),
    ("Morena", {"S": "#B97B52", "s": "#9A6240"}),
    ("Canela", {"S": "#8D5524", "s": "#6F3E17"}),
    ("Oscura", {"S": "#6F4426", "s": "#533019"}),
    ("Muy oscura", {"S": "#4A2C1A", "s": "#35200F"}),
]

HAIR_COLORS = [
    ("Negro", {"H": "#16130F", "h": "#3A332B", "j": "#0B0907"}),
    ("Castaño oscuro", {"H": "#2B1B12", "h": "#4A3022", "j": "#1A0F09"}),
    ("Castaño", {"H": "#5A3A22", "h": "#7B5434", "j": "#3A2314"}),
    ("Cobrizo", {"H": "#B5651D", "h": "#D88A3F", "j": "#7F4410"}),
    ("Pelirrojo", {"H": "#C4451C", "h": "#E86A3A", "j": "#8A2E10"}),
    ("Rubio", {"H": "#E5C76B", "h": "#F3DD99", "j": "#B8963F"}),
    ("Platino", {"H": "#EFE6C8", "h": "#FFFBEA", "j": "#C9BE98"}),
    ("Canoso", {"H": "#8A8F98", "h": "#B8BDC6", "j": "#5E636B"}),
    ("Blanco", {"H": "#E8EAEE", "h": "#FFFFFF", "j": "#B9BDC6"}),
    ("Azul", {"H": "#2F6FE0", "h": "#5E96FF", "j": "#1B4399"}),
    ("Rosa", {"H": "#E85FA8", "h": "#FF8FC6", "j": "#A83A78"}),
    ("Violeta", {"H": "#7B3F9E", "h": "#9C5FC0", "j": "#522A6B"}),
]

EYE_COLORS = [
    ("Café", {"e": "#6B3F1D"}),
    ("Azul", {"e": "#2F7FD8"}),
    ("Verde", {"e": "#2E8B57"}),
    ("Avellana", {"e": "#A27A2C"}),
    ("Gris", {"e": "#7A8794"}),
]

OUTFIT_COLORS = [
    ("Azul", {"O": "#1E8CFF", "o": "#0F5FB8", "A": "#FFFFFF", "a": "#C9D3DD"}),
    ("Naranja", {"O": "#FF7A1A", "o": "#C45A0C", "A": "#FFC21A", "a": "#D99A00"}),
    ("Verde", {"O": "#3C8D4E", "o": "#2A6A3A", "A": "#D9B26A", "a": "#B98B4E"}),
    ("Gris", {"O": "#7A8794", "o": "#55616D", "A": "#E5322A", "a": "#A82020"}),
    ("Cian", {"O": "#2B9BD9", "o": "#1A6F9E", "A": "#FFC21A", "a": "#D99A00"}),
    ("Rojo", {"O": "#D8443A", "o": "#A22E27", "A": "#FFFFFF", "a": "#C9D3DD"}),
    ("Violeta", {"O": "#8B5CF6", "o": "#5E3AB8", "A": "#FFFFFF", "a": "#C9D3DD"}),
    ("Negro", {"O": "#2B2F36", "o": "#15181D", "A": "#FFC21A", "a": "#D99A00"}),
    ("Blanco", {"O": "#F0F3F7", "o": "#C9D3DD", "A": "#1E8CFF", "a": "#0F5FB8"}),
    ("Mostaza", {"O": "#E0A800", "o": "#A87F00", "A": "#2B2F36", "a": "#15181D"}),
]

PANTS_COLORS = [
    ("Azul marino", {"P": "#2B3A55", "p": "#1B2538"}),
    ("Negro", {"P": "#23262B", "p": "#131518"}),
    ("Caqui", {"P": "#B79B68", "p": "#8F7748"}),
    ("Gris", {"P": "#6B7480", "p": "#4A525C"}),
    ("Jean", {"P": "#3E6BA8", "p": "#294A7A"}),
    ("Verde oliva", {"P": "#5E6B3A", "p": "#434D28"}),
]

GLASSES_COLORS = [
    ("Negro", {"F": "#16181C"}),
    ("Dorado", {"F": "#D9A21B"}),
    ("Plateado", {"F": "#B8C2CC"}),
    ("Rojo", {"F": "#D8443A"}),
    ("Azul", {"F": "#1E6FD9"}),
]

HEADWEAR_COLORS = [
    ("Amarillo", {"T": "#FFC21A", "t": "#D99A00", "U": "#FFFFFF"}),
    ("Azul", {"T": "#1E6FD9", "t": "#1348A0", "U": "#FFFFFF"}),
    ("Rojo", {"T": "#D8443A", "t": "#A22E27", "U": "#FFFFFF"}),
    ("Negro", {"T": "#2B2F36", "t": "#15181D", "U": "#FFC21A"}),
    ("Verde", {"T": "#3C8D4E", "t": "#2A6A3A", "U": "#FFFFFF"}),
    ("Café", {"T": "#7A5230", "t": "#553719", "U": "#D9B26A"}),
    ("Blanco", {"T": "#F0F3F7", "t": "#C9D3DD", "U": "#1E8CFF"}),
    ("Violeta", {"T": "#8B5CF6", "t": "#5E3AB8", "U": "#FFFFFF"}),
]

BACKGROUNDS = [
    ("Azul noche", "#0F2A4D"),
    ("Asfalto", "#2A2B30"),
    ("Verde carta", "#1F3A2A"),
    ("Acero", "#2B2F36"),
    ("Cielo", "#06213F"),
    ("Ámbar oscuro", "#4A3410"),
    ("Violeta", "#2E1F4F"),
    ("Borgoña", "#4A1F2B"),
]

# Colores fijos que no cambian con la configuración.
FIXED = {
    "K": "#0A0E13",
    "E": "#14161B",
    "W": "#FFFFFF",
    "M": "#7A2A2A",
    "m": "#C0605A",
    "B": "#5B3A21",
    "b": "#3E2715",
    "L": "#BFE3FF",
    "g": "#FFFFFF",
    "Y": "#FFC21A",
    "R": "#E5322A",
    "C": "#4CC6FF",
    "N": "#7A5230",
    "Z": "#8A99A8",
}

# Marco por rareza (docs/GAMIFICACION.md): color de respaldo y variable CSS.
FRAMES = {
    "common": ("#8D9CAD", "--rarity-common"),
    "rare": ("#1E8CFF", "--rarity-rare"),
    "epic": ("#8B5CF6", "--rarity-epic"),
    "legendary": ("#E0A800", "--rarity-legendary"),
}
