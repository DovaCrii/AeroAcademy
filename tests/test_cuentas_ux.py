"""Mejoras de UX de cuentas (P0-2): cabecera pública, menú de usuario, Mi cuenta, contraseña, espera y D35."""

import pytest
from django.core.cache import cache
from django.test import Client

pytestmark = pytest.mark.django_db
GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite
NEW = "Otra-clave-de-prueba-5530!"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def anon():
    return Client(REMOTE_ADDR="127.0.0.1")


def password_client(person, raw=GOOD):
    person.set_password(raw)
    person.save(update_fields=["password"])
    client = anon()
    assert client.post("/entrar/", {"email": person.login, "password": raw}).status_code == 302
    return client


# --- cabecera pública -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("door", ["tailnet", "public"])
def test_public_header_has_login_and_how_to_get_account(settings, door):
    settings.PUBLIC_DOOR = door == "public"
    for path in ("/bienvenida/", "/entrar/"):
        html = anon().get(path).content.decode()
        assert 'href="/entrar/">Entrar</a>' in html
        assert 'href="/bienvenida/#cuenta">¿Cómo obtengo mi cuenta?</a>' in html
        assert 'id="cuenta"' in html
        assert "enlace personal" in html and "enlace del equipo" in html


def test_public_door_hides_tailscale_copy(settings):
    settings.PUBLIC_DOOR = True
    html = anon().get("/bienvenida/").content.decode()
    assert "Tailscale" not in html
    assert "Solo dentro de la red del equipo" not in html
    settings.PUBLIC_DOOR = False
    html = anon().get("/bienvenida/").content.decode()
    assert "Tailscale" in html
    assert "Solo dentro de la red del equipo" in html
