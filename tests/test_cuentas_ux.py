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


# --- menú de usuario y Mi cuenta ------------------------------------------------------------------------------


def test_user_menu_has_account_and_text_logout_for_password_session(member):
    client = password_client(member)
    html = client.get("/").content.decode()
    assert '<details class="cell usermenu">' in html
    for needle in (
        'href="/perfil/">Mi hoja',
        'href="/perfil/avatar/">Mi avatar',
        'href="/cuenta/">Mi cuenta',
    ):
        assert needle in html, needle
    assert ">Salir</button>" in html
    assert 'aria-label="Salir"' not in html


def test_tailscale_session_has_no_logout_in_menu(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert 'href="/cuenta/">Mi cuenta' in html
    assert ">Salir</button>" not in html


def test_account_page_per_session_kind(client_for, member, lead):
    html = client_for(member.login).get("/cuenta/").content.decode()
    assert member.login in html
    assert "no tienes una contraseña que cambiar" in html
    assert "/cuenta/contrasena/" not in html
    html = password_client(member).get("/cuenta/").content.decode()
    assert 'href="/cuenta/contrasena/"' in html
    assert ">Salir</button>" in html
    # el enlace a 2FA solo existe para lead/admin y solo en la tailnet
    assert "/seguridad/2fa/" not in html
    assert "/seguridad/2fa/" in client_for(lead.login).get("/cuenta/").content.decode()


def test_account_page_hides_2fa_link_in_public_door(settings, lead):
    settings.PUBLIC_DOOR = True
    client = anon()
    lead.set_password(GOOD)
    lead.save(update_fields=["password"])
    client.post("/entrar/", {"email": lead.login, "password": GOOD})
    from apps.accounts import two_factor

    session = client.session
    session[two_factor.SESSION_KEY] = True
    session.save()
    html = client.get("/cuenta/").content.decode()
    assert "Mi cuenta" in html
    assert "/seguridad/2fa/" not in html
    assert "dirección pública" in html


def test_account_requires_login():
    response = anon().get("/cuenta/")
    assert response.status_code == 302 and response.url.startswith("/bienvenida/")


# --- cambio de contraseña ---------------------------------------------------------------------------------------


def test_password_change_requires_old_password_and_csrf(member):
    client = password_client(member)
    data = {"old_password": "equivocada-1234", "new_password1": NEW, "new_password2": NEW}
    bad = client.post("/cuenta/contrasena/", data)
    assert bad.status_code == 200
    member.refresh_from_db()
    assert member.check_password(GOOD)
    ok = client.post("/cuenta/contrasena/", {**data, "old_password": GOOD})
    assert ok.status_code == 302 and ok.url == "/cuenta/"
    member.refresh_from_db()
    assert member.check_password(NEW)
    assert client.get("/cuenta/").status_code == 200  # la sesión sigue abierta
    # sin token CSRF el envío se rechaza
    strict = Client(REMOTE_ADDR="127.0.0.1", enforce_csrf_checks=True)
    member.set_password(GOOD)
    member.save()
    strict.force_login(member, backend="django.contrib.auth.backends.ModelBackend")
    assert strict.post("/cuenta/contrasena/", {**data, "old_password": GOOD}).status_code == 403


def test_password_change_validates_and_limits_attempts(member):
    client = password_client(member)
    weak = client.post(
        "/cuenta/contrasena/",
        {"old_password": GOOD, "new_password1": "123", "new_password2": "123"},
    )
    assert weak.status_code == 200 and "pub-error" in weak.content.decode()
    member.refresh_from_db()
    assert member.check_password(GOOD)
    for _ in range(5):
        client.post(
            "/cuenta/contrasena/",
            {"old_password": "mala-clave-99", "new_password1": NEW, "new_password2": NEW},
        )
    blocked = client.post(
        "/cuenta/contrasena/", {"old_password": GOOD, "new_password1": NEW, "new_password2": NEW}
    )
    assert blocked.status_code == 429
    member.refresh_from_db()
    assert member.check_password(GOOD)


def test_tailscale_session_has_no_password_change(client_for, member):
    client = client_for(member.login)
    assert client.get("/cuenta/contrasena/").status_code == 404
    assert client.post("/cuenta/contrasena/", {"old_password": "x"}).status_code == 404


def test_account_pages_are_constant_in_queries(member, django_assert_max_num_queries):
    client = password_client(member)
    client.get("/cuenta/")
    with django_assert_max_num_queries(25):
        assert client.get("/cuenta/").status_code == 200
