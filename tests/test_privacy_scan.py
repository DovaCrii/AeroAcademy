"""Pruebas de tools/kit/privacy_scan.py (los secretos de prueba se arman por partes)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("privacy_scan", ROOT / "tools/kit/privacy_scan.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def scan_text(tmp_path, text, name="nota.md", config=None):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return ps.scan(tmp_path, config, files=[name])


def test_texto_limpio_pasa(tmp_path):
    assert scan_text(tmp_path, "Hola mundo, contacto: persona@example.com\n") == []


@pytest.mark.parametrize(
    "texto,regla",
    [
        ("KEY=" + "nvapi-" + "A" * 30, "nvapi"),
        ("k = '" + "sk-" + "b1" * 15 + "'", "sk"),
        ("aws " + "AKIA" + "ABCDEFGHIJKLMNOP", "aws"),
        ("-----BEGIN " + "RSA PRIVATE KEY-----", "private-key"),
        ("-----BEGIN " + "PRIVATE KEY-----", "private-key"),
        ("RUT 12.345.678-5 del cliente", "rut"),
        ("rut 11111111-K", "rut"),
        ("escribe a alguien@empresa-real.cl", "email"),
    ],
)
def test_detecta_contenido(tmp_path, texto, regla):
    problemas = scan_text(tmp_path, texto + "\n")
    assert any(p.startswith(regla + ":") for p in problemas), problemas


def test_no_confunde_ssh_ni_numeros(tmp_path):
    texto = "ssh usuario@100.64.0.1\nversion 1.234.567 y 2026-10-13\n"
    assert scan_text(tmp_path, texto) == []


def test_rutas_prohibidas():
    assert ps.check_path("private/dgac/plan.md")
    assert ps.check_path(".env")
    assert ps.check_path("config/.env.production")
    assert ps.check_path("--help")
    assert ps.check_path("sub/--basura.txt")
    assert ps.check_path(".env.example") == []
    assert ps.check_path("docs/private_notes.md") == []


def test_allowlist_de_dominios_y_reglas(tmp_path):
    texto = "contacto@lev-fixture.cl\n"
    assert scan_text(tmp_path, texto)
    assert scan_text(tmp_path, texto, config={"allow_email_domains": ["lev-fixture.cl"]}) == []
    cfg = {"allow_rules": {"nota.md": ["email"]}}
    assert scan_text(tmp_path, texto, config=cfg) == []
    # la excepción de una regla no apaga las demás
    otra = texto + "KEY=" + "nvapi-" + "Z" * 30 + "\n"
    assert any(p.startswith("nvapi:") for p in scan_text(tmp_path, otra, config=cfg))


def test_ignora_binarios(tmp_path):
    (tmp_path / "x.bin").write_bytes(b"\0" + b"nvapi-" + b"A" * 30)
    assert ps.scan(tmp_path, files=["x.bin"]) == []


def test_el_repositorio_pasa_la_revision():
    import json

    cfg = json.loads((ROOT / ".privacy-scan.json").read_text(encoding="utf-8"))
    assert ps.scan(ROOT, cfg) == []
