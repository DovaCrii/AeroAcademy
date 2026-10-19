"""Puerta pública con Tailscale Funnel (D36): identidad ignorada, sin admin, TOTP para lead y admin, límites de
intentos, cabeceras y archivos de despliegue."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts import services, totp, two_factor
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def public(settings):
    settings.PUBLIC_DOOR = True
    settings.PUBLIC_REQUIRE_SECOND_FACTOR = (
        True  # D36: el endurecimiento completo; por defecto está apagado (D39)
    )
    return settings


def anon(**extra):
    """Navegador que llega por el proxy local (Funnel) sin identidad."""
    return Client(REMOTE_ADDR="127.0.0.1", **extra)


def with_password(person, raw=GOOD):
    person.set_password(raw)
    person.save(update_fields=["password"])
    return person


def password_login(client, person, raw=GOOD):
    return client.post("/entrar/", {"email": person.login, "password": raw})


def enrol(person):
    """Deja el TOTP activado y devuelve (secreto, códigos de recuperación)."""
    device = two_factor.begin_enrollment(person)
    codes = two_factor.confirm_enrollment(person, totp.code_at(device.secret))
    assert codes
    device.refresh_from_db()
    return device.secret, codes


def next_code(secret, device_person):
    """Un código válido y posterior al último usado (el siguiente paso de 30 s)."""
    import time

    return totp.code_at(secret, time.time() + totp.STEP_SECONDS)


# --- TOTP (RFC 6238) ------------------------------------------------------------------------------------------


def test_totp_matches_the_rfc_6238_vectors():
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp.code_at(secret, 59, digits=8) == "94287082"
    assert totp.code_at(secret, 1111111109, digits=8) == "07081804"
    assert totp.code_at(secret, 20000000000, digits=8) == "65353130"


def test_totp_window_replay_and_format():
    secret = totp.new_secret()
    now = 1_700_000_000
    code = totp.code_at(secret, now)
    counter = totp.counter_for(now)
    assert totp.verify(secret, code, moment=now) == counter
    assert totp.verify(secret, code, moment=now + 30) == counter  # un paso de desfase
    assert totp.verify(secret, code, moment=now + 90) is None  # fuera de la ventana
    assert totp.verify(secret, code, moment=now, after_counter=counter) is None  # ya usado
    assert totp.verify(secret, " " + code[:3] + " " + code[3:], moment=now) == counter
    assert totp.verify(secret, "12345", moment=now) is None
    assert totp.verify(secret, "abcdef", moment=now) is None


def test_otpauth_uri_has_secret_and_issuer():
    uri = totp.otpauth_uri("ABCDEFGH", "ana@example.com")
    assert uri.startswith("otpauth://totp/AeroAcademy%3Aana%40example.com?")
    assert "secret=ABCDEFGH" in uri and "issuer=AeroAcademy" in uri


# --- identidad en cada puerta -------------------------------------------------------------------------------


def test_tailnet_door_is_unchanged(member):
    response = tailscale_client(member.login).get("/")
    assert response.status_code == 200
    assert getattr(response.wsgi_request, "public_door", None) is False


def test_header_is_ignored_on_the_public_door(public, member):
    response = tailscale_client(member.login).get("/")  # trae Tailscale-User-Login válido
    assert response.status_code == 302 and response.url.startswith("/bienvenida/")
    assert response.wsgi_request.public_door is True
    assert "HTTP_TAILSCALE_USER_LOGIN" not in response.wsgi_request.META
    assert not response.wsgi_request.user.is_authenticated


def test_header_does_not_create_people_on_the_public_door(public):
    from apps.accounts.models import Person

    tailscale_client("nuevo@example.com", name="Nuevo").get("/")
    assert not Person.objects.filter(login="nuevo@example.com").exists()


def test_a_tailscale_session_is_not_accepted_on_the_public_door(public, member):
    client = anon()
    client.force_login(member, backend="apps.accounts.backends.TailscaleBackend")
    response = client.get("/")
    assert response.status_code == 302 and response.url.startswith("/bienvenida/")


def test_dev_remote_user_is_ignored_on_the_public_door(public, member, settings):
    settings.DEBUG = True
    settings.DEV_REMOTE_USER = member.login
    assert anon().get("/").status_code == 302


def test_public_door_needs_the_local_proxy(public, member):
    assert Client(REMOTE_ADDR="203.0.113.9").get("/bienvenida/").status_code == 403


def test_password_login_works_on_the_public_door(public, member):
    with_password(member)
    client = anon()
    assert client.get("/bienvenida/").status_code == 200
    response = password_login(client, member)
    assert response.status_code == 302 and response.url == "/"
    assert client.get("/").status_code == 200


def test_team_signup_link_works_on_the_public_door(public, admin_person):
    from apps.accounts import team_link

    url = team_link.generate(admin_person)
    token = url.rstrip("/").rsplit("/", 1)[1]
    assert anon().get(f"/inscripcion/{token}/").status_code == 200


# --- puertas cerradas ------------------------------------------------------------------------------------------


def test_admin_and_moderation_are_404_on_the_public_door(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    client = anon()
    password_login(client, admin_person)
    client.post("/verificar/", {"code": next_code(secret, admin_person)})
    for path in (
        "/admin/",
        "/admin/login/",
        "/moderacion/",
        "/equipo/personas/",
        "/seguridad/2fa/",
    ):
        assert client.get(path).status_code == 404, path
    assert anon().get("/admin/").status_code == 404  # tampoco sin sesión


def test_admin_still_answers_on_the_tailnet_door(admin_person):
    assert tailscale_client(admin_person.login).get("/admin/").status_code == 200
    assert tailscale_client(admin_person.login).get("/moderacion/").status_code == 200


# --- segundo factor ------------------------------------------------------------------------------------------


def test_lead_and_admin_enter_with_the_password_alone_by_default(settings, lead, admin_person):
    """D39: sin PUBLIC_REQUIRE_SECOND_FACTOR no hay pantalla de bloqueo ni código para lead y admin."""
    settings.PUBLIC_DOOR = True
    assert settings.PUBLIC_REQUIRE_SECOND_FACTOR is False
    for person in (lead, admin_person):
        with_password(person)
        client = anon()
        assert password_login(client, person).status_code == 302
        assert client.get("/").status_code == 200
        assert client.get("/rutas/").status_code == 200
        assert (
            client.get("/admin/").status_code == 404
        )  # lo de administración sigue sin existir en internet


def test_lead_without_totp_is_blocked_on_the_public_door(public, lead):
    with_password(lead)
    client = anon()
    assert password_login(client, lead).status_code == 302
    response = client.get("/")
    assert response.status_code == 403
    assert "segundo factor" in response.content.decode().lower()
    assert client.get("/rutas/").status_code == 403


def test_admin_must_pass_totp_on_the_public_door(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    client = anon()
    password_login(client, admin_person)
    response = client.get("/")
    assert response.status_code == 302 and response.url.startswith("/verificar/")
    bad = client.post("/verificar/", {"code": "000000"})
    assert bad.status_code == 400
    assert client.get("/").status_code == 302  # sigue sin pasar
    ok = client.post("/verificar/", {"code": next_code(secret, admin_person)})
    assert ok.status_code == 302 and ok.url == "/"
    assert client.get("/").status_code == 200


def test_totp_code_cannot_be_replayed(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    code = next_code(secret, admin_person)
    first = anon()
    password_login(first, admin_person)
    assert first.post("/verificar/", {"code": code}).status_code == 302
    second = anon()
    password_login(second, admin_person)
    assert second.post("/verificar/", {"code": code}).status_code == 400


def test_second_login_asks_for_the_code_again(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    client = anon()
    password_login(client, admin_person)
    client.post("/verificar/", {"code": next_code(secret, admin_person)})
    client.post("/salir/")
    password_login(client, admin_person)
    assert client.get("/").status_code == 302


def test_recovery_code_works_once(public, admin_person):
    with_password(admin_person)
    _, codes = enrol(admin_person)
    client = anon()
    password_login(client, admin_person)
    assert client.post("/verificar/", {"code": codes[0]}).status_code == 302
    assert client.get("/").status_code == 200
    other = anon()
    password_login(other, admin_person)
    assert other.post("/verificar/", {"code": codes[0]}).status_code == 400
    assert two_factor.recovery_left(admin_person) == two_factor.RECOVERY_COUNT - 1


def test_recovery_codes_are_stored_hashed(admin_person):
    from apps.accounts.models import TotpDevice

    _, codes = enrol(admin_person)
    stored = TotpDevice.objects.get(person=admin_person).recovery_hashes
    assert len(stored) == len(codes) and not set(stored) & set(codes)


def test_member_does_not_need_totp_on_the_public_door(public, member):
    with_password(member)
    client = anon()
    password_login(client, member)
    assert client.get("/").status_code == 200


def test_verify_next_is_validated(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    for evil in ("//evil.com", "/\\evil.com", "https://evil.com"):
        two_factor.TotpDevice.objects.filter(person=admin_person).update(last_counter=0)
        client = anon()
        password_login(client, admin_person)
        response = client.post(
            "/verificar/", {"code": next_code(secret, admin_person), "next": evil}
        )
        assert response.status_code == 302 and response.url == "/"
    two_factor.TotpDevice.objects.filter(person=admin_person).update(last_counter=0)
    client = anon()
    password_login(client, admin_person)
    ok = client.post("/verificar/", {"code": next_code(secret, admin_person), "next": "/rutas/"})
    assert ok.url == "/rutas/"


def test_enrolment_page_works_on_the_tailnet_only(public, settings, lead):
    settings.PUBLIC_DOOR = False
    client = tailscale_client(lead.login)
    page = client.get("/seguridad/2fa/")
    assert page.status_code == 200
    secret = two_factor.TotpDevice.objects.get(person=lead).secret
    assert totp.group(secret) in page.content.decode()
    wrong = client.post("/seguridad/2fa/", {"action": "confirm", "code": "000000"})
    assert "incorrecto" in wrong.content.decode()
    assert not two_factor.is_enrolled(lead)
    done = client.post("/seguridad/2fa/", {"action": "confirm", "code": totp.code_at(secret)})
    assert done.status_code == 200 and "se vuelven a mostrar" in done.content.decode()
    assert two_factor.is_enrolled(lead)
    settings.PUBLIC_DOOR = True
    assert anon().get("/seguridad/2fa/").status_code == 404


def test_enrolment_requires_post_and_csrf_for_changes(lead):
    client = Client(
        REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=lead.login, enforce_csrf_checks=True
    )
    response = client.post("/seguridad/2fa/", {"action": "disable", "code": "123456"})
    assert response.status_code == 403


# --- límites de intentos ---------------------------------------------------------------------------------------


def test_password_attempts_are_limited_on_the_public_door(public, member):
    with_password(member)
    client = anon()
    for _ in range(services.LOGIN_MAX_FAILURES):
        assert (
            client.post("/entrar/", {"email": member.login, "password": "mala"}).status_code == 200
        )
    assert client.post("/entrar/", {"email": member.login, "password": GOOD}).status_code == 429


def test_totp_attempts_are_limited(public, admin_person):
    with_password(admin_person)
    secret, _ = enrol(admin_person)
    client = anon()
    password_login(client, admin_person)
    for _ in range(two_factor.MAX_FAILURES):
        assert client.post("/verificar/", {"code": "000000"}).status_code == 400
    blocked = client.post("/verificar/", {"code": next_code(secret, admin_person)})
    assert blocked.status_code == 429
    assert client.get("/").status_code == 302  # y el código bueno tampoco pasó


def test_signup_link_attempts_are_limited(public, member):
    token = services.issue_signup_token(member)
    client = anon()
    for _ in range(20):
        client.post(f"/registro/{token}/", {})
    assert client.post(f"/registro/{token}/", {}).status_code == 429


def test_client_ip_uses_the_last_forwarded_value_on_the_public_door(public, member):
    from apps.accounts.views import _client_ip

    request = anon(HTTP_X_FORWARDED_FOR="6.6.6.6, 198.51.100.7").get("/bienvenida/").wsgi_request
    assert _client_ip(request) == "198.51.100.7"
    request = anon(HTTP_X_FORWARDED_FOR="basura").get("/bienvenida/").wsgi_request
    assert _client_ip(request) == "127.0.0.1"


# --- configuración y despliegue --------------------------------------------------------------------------------


def _prod_settings(**env):
    base = {
        k: v
        for k, v in os.environ.items()
        if k not in {"AEROACADEMY_DOOR", "CACHE_DIR", "PUBLIC_HTTPS_PORT"}
    }
    base.update(SECRET_KEY="x" * 40, ALLOWED_HOSTS="aeroacademy.ts.net", **env)
    code = (
        "import config.settings.prod as s;"
        "print(s.PUBLIC_DOOR, s.CSRF_TRUSTED_ORIGINS, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE,"
        " getattr(s, 'SECURE_HSTS_SECONDS', 0), getattr(s, 'SESSION_COOKIE_NAME', 'sessionid'), s.X_FRAME_OPTIONS, s.SECURE_REFERRER_POLICY,"
        " s.CACHES['default']['BACKEND'].rsplit('.', 1)[-1])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=base, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def test_prod_settings_public_door_headers_and_cookies():
    line = _prod_settings(AEROACADEMY_DOOR="public", PUBLIC_HTTPS_PORT="8443")
    assert line == (
        "True ['https://aeroacademy.ts.net'] True True 31536000 aa_public_sid DENY same-origin "
        "FileBasedCache"
    )


def test_prod_settings_tailnet_door_keeps_its_port_and_shared_cache():
    line = _prod_settings(PUBLIC_HTTPS_PORT="8443")
    assert line.startswith("False ['https://aeroacademy.ts.net:8443'] True True 0 sessionid")
    assert line.endswith("FileBasedCache")  # nunca por proceso en producción


def test_public_unit_and_installer_are_wired_and_funnel_is_opt_in():
    unit = (DEPLOY / "centro-public.service").read_text(encoding="utf-8")
    assert "--bind 127.0.0.1:8011" in unit and "AEROACADEMY_DOOR=public" in unit
    assert "--no-control-socket" in unit and "NoNewPrivileges=true" in unit
    assert "127.0.0.1:8010" in (DEPLOY / "centro.service").read_text(encoding="utf-8")
    assert "AEROACADEMY_DOOR" not in (DEPLOY / "centro.service").read_text(encoding="utf-8")
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert 'FUNNEL="${PUBLIC_FUNNEL:-0}"' in install  # apagado por defecto
    lines = [ln.split("#", 1)[0] for ln in install.splitlines()]
    funnel = [ln for ln in lines if "funnel" in ln.lower() and not ln.strip().startswith("echo")]
    assert any('"${TS[@]}" funnel --bg --https=443' in ln for ln in funnel)
    assert all('"${TS[@]}"' in ln or "FUNNEL" in ln or "funnel.service" in ln for ln in funnel)
    assert "serve reset" in install and "PUBLIC_FUNNEL=1 solo se permite" in install
