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


# --- pantalla de espera -------------------------------------------------------------------------------------------


def test_waiting_page_has_logout_for_password_session(make_person):
    pending = make_person("pend@example.com")
    client = password_client(pending)
    pending.status = "pending"  # la persona entró aprobada y después quedó en espera
    pending.save(update_fields=["status"])
    html = client.get("/espera/").content.decode()
    assert "Esperando aprobación" in html
    assert "con tu correo y tu contraseña" in html
    assert "Te avisamos en la campana" in html and "escríbele al administrador" in html
    assert ">Salir</button>" in html
    # «Salir» funciona estando en espera y cierra la sesión
    response = client.post("/salir/")
    assert response.status_code == 302 and response.url == "/bienvenida/"
    assert client.get("/espera/").status_code == 302


def test_waiting_page_for_tailscale_has_no_logout(client_for, make_person):
    pending = make_person("pend2@example.com", status="pending")
    html = client_for(pending.login).get("/espera/").content.decode()
    assert "Tailscale" in html and "Te avisamos en la campana" in html
    assert ">Salir</button>" not in html


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


# --- Equipo → Personas: paso a paso ------------------------------------------------------------------------------


def test_people_page_has_step_by_step_for_admin_only(client_for, admin_person, lead, member):
    html = client_for(admin_person.login).get("/equipo/personas/").content.decode()
    assert "Cómo dar de alta a una persona" in html
    assert html.count("<li><b>") >= 4
    assert "Generar enlace de registro" in html
    assert "Copiar enlace de registro" not in html
    assert "Solo funciona dentro de la tailnet" not in html
    lead_html = client_for(lead.login).get("/equipo/personas/").content.decode()
    assert "Cómo dar de alta a una persona" not in lead_html


# --- bitácora de los comandos de alta ----------------------------------------------------------------------------


def test_commands_log_to_moderation(member, make_person):
    from io import StringIO

    from django.core.management import call_command

    from apps.community.models import ModerationLog

    out = StringIO()
    call_command("aprobar", "nueva@example.com", "--rol", "member", stdout=out)
    call_command("enlace_registro", member.login, stdout=out)
    call_command("enlace_equipo", "--dias", "7", stdout=out)
    call_command("enlace_equipo", "--revocar", stdout=out)
    entries = list(ModerationLog.objects.order_by("id").values_list("action", "actor", "summary"))
    assert [e[0] for e in entries] == [
        "approve_person",
        "signup_link",
        "team_link",
        "team_link_revoke",
    ]
    assert all(e[1] is None and "(consola)" in e[2] for e in entries)
    # nunca el enlace ni su secreto
    printed = out.getvalue()
    token = printed.split("/inscripcion/")[1].split()[0].rstrip("/")
    secret_link = printed.split("/registro/")[1].split()[0].rstrip("/")
    dump = " ".join(" ".join(map(str, e)) for e in entries)
    assert token not in dump and secret_link not in dump and "http" not in dump


@pytest.mark.parametrize("evil", ["//evil.com/x", "/\\evil.com", "https://evil.com/"])
def test_next_rejects_evil(member, evil):
    member.set_password(GOOD)
    member.save(update_fields=["password"])
    response = anon().post("/entrar/", {"email": member.login, "password": GOOD, "next": evil})
    assert response.status_code == 302 and response.url == "/"
    ok = anon().post("/entrar/", {"email": member.login, "password": GOOD, "next": "/rutas/"})
    assert ok.url == "/rutas/"
