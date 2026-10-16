"""Herramientas para dibujar piezas HD: validador (`validate_hd`) y hoja de contactos (`preview_avatar --hd`)."""

import importlib.util
import sys
from pathlib import Path

import pytest
from django.conf import settings

from apps.gamification.avatar import hd
from apps.gamification.avatar.validation import validate_hd

ROOT = Path(settings.BASE_DIR)


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_registered_hd_pieces_validate():
    assert validate_hd() == []


@pytest.mark.parametrize(
    ("category", "option", "art", "message"),
    [
        ("eyes", "no-existe", hd.sprite((24, 22), ["EE"]), "no es una opción"),
        ("eyes", "dot", hd.sprite((24, 22), ["E1"]), "claves del motor"),
        ("eyes", "dot", hd.sprite((24, 22), ["E?"]), "fuera de la paleta"),
        ("eyes", "dot", hd.sprite((24, 22), ["EE", "E"]), "lo mismo"),
        ("eyes", "dot", hd.sprite((0, 0), ["EE"]), "sale de su zona"),
        ("eyes", "dot", hd.sprite((24, 22), ["EE"], space="stage"), "espacio"),
        ("prop", "tablet", hd.sprite((40, 30), ["KK"] * 20, space="stage"), "ventana de la cara"),
    ],
)
def test_validator_catches_bad_pieces(monkeypatch, category, option, art, message):
    monkeypatch.setitem(hd.HD, category, {option: art})
    assert any(message in error for error in validate_hd([category]))


def test_validator_limits_colors(monkeypatch):
    many = hd.sprite((24, 22), ["KSEeWMmYRCNZG"])
    monkeypatch.setitem(hd.HD["eyes"], "dot", many)
    assert any("colores" in error for error in validate_hd(["eyes"]))


def test_hd_contact_sheet_is_written(tmp_path):
    tool = load_tool("preview_avatar")
    out = tmp_path / "hoja.png"
    assert tool.main([str(out), "--hd", "--careers", "cartographer", "pilot", "scale=1"]) == 0
    assert out.read_bytes().startswith(b"\x89PNG")
    sheet = tmp_path / "gorros.png"
    assert tool.main([str(sheet), "--hd", "--sheet", "headwear", "scale=1", "pose=wave"]) == 0
    assert sheet.stat().st_size > 1000


def test_validate_tool_accepts_hd_categories():
    tool = load_tool("validate_part")
    assert tool.main(["hd"]) == 0 and tool.main(["hd:eyes", "hair"]) == 0
    assert tool.main(["hd:nada"]) == 1
