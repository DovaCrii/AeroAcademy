"""Valida piezas de avatar. Uso (desde la raíz del repositorio):

    python tools/validate_part.py hair            # una categoría
    python tools/validate_part.py hair eyes brows # varias
    python tools/validate_part.py                 # todas
    python tools/validate_part.py hd:eyes hd:headwear   # piezas HD de una categoría
    python tools/validate_part.py hd              # todas las piezas HD

Categorías: hair, eyes, brows, mouths, facial_hair, headwear, glasses, outfits, neckwear.
Sale con código 1 si hay errores.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.gamification.avatar.validation import SPECS, validate_all, validate_hd  # noqa: E402


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252
    wanted = argv or list(SPECS)
    hd_wanted = [c.split(":", 1)[1] for c in wanted if c.startswith("hd:")]
    run_hd = "hd" in wanted or bool(hd_wanted) or not argv
    wanted = [c for c in wanted if c != "hd" and not c.startswith("hd:")]
    if argv and not wanted and run_hd:
        wanted = []
    unknown = [c for c in wanted if c not in SPECS]
    if unknown:
        print("categorías desconocidas:", ", ".join(unknown), "· válidas:", ", ".join(SPECS))
        return 2
    errors = validate_all(wanted) + (validate_hd(hd_wanted or None) if run_hd else [])
    wanted = wanted + (["hd"] if run_hd else [])
    for error in errors:
        print("✗", error)
    print(
        f"{'✔ sin errores' if not errors else f'{len(errors)} error(es)'} en: {', '.join(wanted)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
