"""Pines de solapa HD (HD-7): brújula, casquito de obra y teodolito dorado, de 7×7 celdas (el de 32 medía 4×4).

Van en el pecho, x 38..44 · y 42..48 (la zona del pin de 32 ×2). Se desbloquean por nivel; el pin nunca lleva texto.
Claves fijas: `K W Y R C Z`.
"""

from . import HD, sprite

HD["pin"].update(
    {
        "compass": sprite(
            (38, 42),
            [
                "..KKK..",
                ".KWWRK.",
                "KWWWRWK",
                "KWWRWWK",
                "KWRWWWK",
                ".KWWWK.",
                "..KKK..",
            ],
        ),
        "hardhat_pin": sprite(
            (38, 43),
            [
                "..YYY..",
                ".KYWYK.",
                "KYYYYYK",
                "KKKKKKK",
            ],
        ),
        "theodolite_pin": sprite(
            (38, 42),
            [
                "..KYK..",
                ".KYWYK.",
                "..KYK..",
                "..KYK..",
                ".KYYYK.",
                "KY.Y.YK",
                "K..Y..K",
            ],
        ),
    }
)
