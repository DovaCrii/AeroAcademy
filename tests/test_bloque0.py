from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

EXPECTED_APPS = {
    "core",
    "accounts",
    "catalog",
    "paths",
    "progress",
    "community",
    "credentials",
    "team",
    "gamification",
    "notifications",
    "assistant",
}


def test_smoke():
    assert settings.SETTINGS_MODULE == "config.settings.dev"


def test_all_project_apps_are_installed():
    assert EXPECTED_APPS <= {config.label for config in apps.get_app_configs()}


def test_home_renders_with_brand(member_client):
    response = member_client.get("/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "AeroAcademy" in html
    assert "Academia LEV Digital 101" in html


def test_base_template_has_responsive_and_theme_hooks(member_client):
    html = member_client.get("/").content.decode()
    assert 'name="viewport"' in html
    assert 'id="themeBtn"' in html
    assert "core/tokens.css" in html
    assert 'lang="es"' in html


def test_base_template_has_empty_slots_for_later_blocks(member_client):
    html = member_client.get("/").content.decode()
    for slot in ("player", "bell"):
        assert f'data-slot="{slot}"' in html


def test_tokens_define_light_and_dark_and_game_layer():
    css = (Path(settings.BASE_DIR) / "apps/core/static/core/tokens.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme:dark" in css
    assert ':root[data-theme="dark"]' in css
    assert "--rarity-epic" in css
    assert "--font-px" in css


def test_local_archivo_font_is_present():
    font = Path(settings.BASE_DIR) / "apps/core/static/core/fonts/Archivo.woff2"
    assert font.is_file() and font.stat().st_size > 0


@pytest.mark.django_db
def test_sqlite_uses_wal():
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
    # En memoria SQLite informa "memory"; con archivo debe ser "wal".
    assert mode in {"wal", "memory"}


def test_prod_settings_require_secret_key_and_hosts(monkeypatch):
    import importlib
    import sys

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.prod")
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)


def test_prod_settings_are_safe(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "x" * 50)
    monkeypatch.setenv("ALLOWED_HOSTS", "academia.tailnet.ts.net")
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    prod = importlib.import_module("config.settings.prod")
    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_TRUSTED_ORIGINS == ["https://academia.tailnet.ts.net"]
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
