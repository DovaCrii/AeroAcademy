"""Avatares pixel-art por capas (32×32). API pública; el detalle está en `engine.py`."""

from .art import GRID
from .engine import (
    CLASS_LABELS,
    CLASSES,
    DEFAULTS,
    UNLOCKS,
    apply_career,
    catalog,
    clean_config,
    compose,
    default_config,
    palette_for,
    render_svg,
    surprise,
)

__all__ = [
    "CLASSES",
    "CLASS_LABELS",
    "DEFAULTS",
    "GRID",
    "UNLOCKS",
    "apply_career",
    "surprise",
    "catalog",
    "clean_config",
    "compose",
    "default_config",
    "palette_for",
    "render_svg",
]
