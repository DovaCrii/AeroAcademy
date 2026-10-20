"""«Salir» para todas las sesiones (D41): con Tailscale deja una bandera que desactiva el ingreso automático
hasta «Entrar con Tailscale»; la bandera no da acceso a nada y la puerta pública la ignora."""

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.middleware import TS_SIGNED_OUT

pytestmark = pytest.mark.django_db
LOGOUT = ">Salir</button>"
GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite
TS_BUTTON = "Entrar con Tailscale"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def password_client(person, **extra):
    person.set_password(GOOD)
    person.save(update_fields=["password"])
    client = Client(REMOTE_ADDR="127.0.0.1", **extra)
    assert client.post("/entrar/", {"email": person.login, "password": GOOD}).status_code == 302
    return client


def test_tailscale_session_shows_logout(client_for, member):
    assert LOGOUT in client_for(member.login).get("/").content.decode()


def test_password_session_shows_logout(member):
    assert LOGOUT in password_client(member).get("/").content.decode()


def test_logout_from_tailscale_leaves_flag_and_blocks_auto_login(client_for, member):
    client = client_for(member.login)
    assert client.get("/").status_code == 200
    response = client.post("/salir/")
    assert response.status_code == 302 and response.url == "/bienvenida/"
    assert client.session.get(TS_SIGNED_OUT) is True
    # el encabezado sigue llegando, pero ya no inicia sesión solo
    page = client.get("/bienvenida/")
    html = page.content.decode()
    assert page.status_code == 200 and TS_BUTTON in html
    assert client.get("/").status_code == 302  # pide entrar
    assert client.get("/").url.startswith("/bienvenida/")
    assert TS_BUTTON in client.get("/entrar/").content.decode()


def test_enter_with_tailscale_clears_flag_and_signs_in_again(client_for, member):
    client = client_for(member.login)
    client.get("/")
    client.post("/salir/")
    response = client.post("/entrar/tailscale/")
    assert response.status_code == 302 and response.url == "/"
    assert TS_SIGNED_OUT not in client.session
    assert client.get("/").status_code == 200
    assert LOGOUT in client.get("/").content.decode()


def test_enter_with_tailscale_keeps_a_safe_next_only(client_for, member):
    client = client_for(member.login)
    client.post("/salir/")
    assert client.post("/entrar/tailscale/", {"next": "/rutas/"}).url == "/rutas/"
    for bad in ("//evil.com", "/\\evil.com", "https://evil.com"):
        client.post("/salir/")
        assert client.post("/entrar/tailscale/", {"next": bad}).url == "/"


def test_get_never_sets_or_clears_the_flag(client_for, member):
    client = client_for(member.login)
    client.get("/")
    assert client.get("/salir/").status_code == 405
    assert TS_SIGNED_OUT not in client.session
    assert client.get("/?sign_out=1&ts_signed_out=1").status_code == 200
    client.post("/salir/")
    assert client.get("/entrar/tailscale/").status_code == 405
    assert client.session.get(TS_SIGNED_OUT) is True


def test_flag_cannot_be_forced_by_headers_or_cookies_of_others(client_for, member):
    # sin POST /salir/ propio, ningún encabezado ni parámetro activa la bandera
    client = client_for(member.login)
    client.get("/", HTTP_TS_SIGNED_OUT="1", HTTP_X_TS_SIGNED_OUT="1")
    assert TS_SIGNED_OUT not in client.session
    assert client.get("/").status_code == 200


def test_flag_requires_csrf_for_the_enter_button(member):
    client = Client(
        REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login, enforce_csrf_checks=True
    )
    assert client.post("/salir/").status_code == 403
    assert client.post("/entrar/tailscale/").status_code == 403


def test_untrusted_proxy_still_gets_403_even_with_the_flag(member):
    client = Client(REMOTE_ADDR="203.0.113.9", HTTP_TAILSCALE_USER_LOGIN=member.login)
    assert client.get("/bienvenida/").status_code == 403
    assert client.post("/entrar/tailscale/").status_code == 403


def test_password_session_is_kept_and_header_does_not_override_it(client_for, make_person, member):
    other = make_person("otra@example.com")
    client = password_client(member, HTTP_TAILSCALE_USER_LOGIN=other.login)
    assert client.get("/cuenta/").status_code == 200
    assert member.login in client.get("/cuenta/").content.decode()


def test_logout_of_a_password_session_in_tailnet_also_stops_header_auto_login(member):
    client = password_client(member, HTTP_TAILSCALE_USER_LOGIN=member.login)
    assert client.post("/salir/").status_code == 302
    assert client.get("/").status_code == 302  # el encabezado no la devuelve a entrar sola
    assert TS_BUTTON in client.get("/bienvenida/").content.decode()
    client.post("/entrar/tailscale/")
    assert client.get("/").status_code == 200


def test_public_door_ignores_flag_header_and_button(settings, member):
    settings.PUBLIC_DOOR = True
    client = Client(REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login)
    assert client.get("/").status_code == 302  # el encabezado se descarta
    html = client.get("/bienvenida/").content.decode()
    assert TS_BUTTON not in html
    assert client.post("/entrar/tailscale/").status_code == 404
    assert client.get("/entrar/tailscale/").status_code == 404
    client.post("/salir/")
    assert TS_SIGNED_OUT not in client.session  # en la puerta pública no se deja bandera
    assert TS_BUTTON not in client.get("/entrar/").content.decode()


def test_anonymous_welcome_without_flag_has_no_tailscale_button(settings):
    html = Client(REMOTE_ADDR="127.0.0.1").get("/bienvenida/").content.decode()
    assert TS_BUTTON not in html
    assert "Entrar</button>" in html


def test_suspended_person_can_still_log_out(client_for, make_person):
    suspended = make_person("susp@example.com", status="suspended")
    client = client_for(suspended.login)
    page = client.get("/")
    assert page.status_code == 403 and LOGOUT in page.content.decode()
    assert client.post("/salir/").status_code == 302
