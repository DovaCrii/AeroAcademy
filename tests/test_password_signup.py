"""Invitación + contraseña dentro de la tailnet (D34): enlace de registro, entrar/salir, límite de intentos,
bienvenida pública y convivencia con la identidad de Tailscale."""

import logging
from io import StringIO
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from apps.accounts import services
from apps.accounts.models import Person, PersonStatus
from apps.team import onboarding
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db

GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite


def anon(**extra):
    """Navegador sin identidad de Tailscale (equipo compartido): llega por el proxy local, sin encabezado."""
    return Client(REMOTE_ADDR="127.0.0.1", **extra)


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def invited(make_person):
    return make_person("nueva@empresa.cl")


def set_password(person, raw=GOOD):
    person.set_password(raw)
    person.save(update_fields=["password"])
    return person


def session_person_id(client):
    return client.session.get("_auth_user_id")


# --- token: un solo uso, vencimiento, manipulación ------------------------------------------------


def test_token_resolves_to_the_person(invited):
    token = services.issue_signup_token(invited)
    assert services.resolve_signup_token(token).pk == invited.pk


def test_token_is_single_use(invited):
    token = services.issue_signup_token(invited)
    person = services.resolve_signup_token(token)
    services.complete_signup(person, display_name="Nueva", password=GOOD)
    assert services.resolve_signup_token(token) is None


def test_new_link_invalidates_the_previous_one(invited):
    first = services.issue_signup_token(invited)
    second = services.issue_signup_token(invited)
    assert services.resolve_signup_token(first) is None
    assert services.resolve_signup_token(second).pk == invited.pk


def test_token_expires_after_seven_days(invited, monkeypatch):
    token = services.issue_signup_token(invited)
    import time

    now = time.time()
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: now + 7 * 86400 - 60))
    assert services.resolve_signup_token(token) is not None
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: now + 7 * 86400 + 60))
    assert services.resolve_signup_token(token) is None


def test_tampered_tokens_are_rejected(invited, make_person):
    token = services.issue_signup_token(invited)
    other = make_person("otra@empresa.cl")
    swapped = token.replace(f"{invited.pk}.", f"{other.pk}.", 1)
    flipped = token[:-1] + ("A" if token[-1] != "A" else "B")
    for bad in (swapped, flipped, token + "x", token[: len(token) // 2], "", "basura", "a:b:c"):
        assert services.resolve_signup_token(bad) is None


def test_token_signed_with_another_salt_is_rejected(invited):
    forged = signing.TimestampSigner().sign(f"{invited.pk}.abc.def")
    assert services.resolve_signup_token(forged) is None


def test_changing_the_password_elsewhere_invalidates_the_link(invited):
    token = services.issue_signup_token(invited)
    set_password(invited)
    assert services.resolve_signup_token(token) is None


def test_link_dies_if_the_person_is_suspended_or_inactive(invited):
    token = services.issue_signup_token(invited)
    services.suspend(invited)
    assert services.resolve_signup_token(token) is None


@pytest.mark.parametrize("status", ["pending", "suspended"])
def test_no_link_for_pending_or_suspended(make_person, status):
    person = make_person("x@empresa.cl", status=status)
    with pytest.raises(ValueError):
        services.issue_signup_token(person)


def test_the_database_never_stores_the_token(invited):
    token = services.issue_signup_token(invited)
    invited.refresh_from_db()
    assert token not in invited.invite_nonce and token != invited.password


# --- solo el admin crea enlaces y agrega personas ---------------------------------------------------


def test_admin_generates_link_and_sees_it_once(admin_person, invited, client_for):
    c = client_for(admin_person.login)
    response = c.post(f"/equipo/personas/{invited.pk}/enlace/")
    assert response.status_code == 302
    page = c.get("/equipo/personas/").content.decode()
    assert "/registro/" in page and "Copiar enlace de registro" in page
    link = page.split("/registro/")[1].split("/")[0]
    assert services.resolve_signup_token(link).pk == invited.pk
    again = c.get("/equipo/personas/").content.decode()
    assert link not in again  # se muestra una sola vez


def test_link_goes_into_the_copyable_invitation(admin_person, invited, client_for):
    c = client_for(admin_person.login)
    c.post(f"/equipo/personas/{invited.pk}/enlace/")
    page = c.get("/equipo/personas/").content.decode()
    assert page.count("/registro/") >= 2  # el recuadro del enlace y el texto de invitación


@pytest.mark.parametrize("role", ["lead", "member"])
def test_only_admin_can_create_links(role, make_person, invited, client_for):
    person = make_person(f"{role}x@lev.cl", role=role)
    c = client_for(person.login)
    assert c.post(f"/equipo/personas/{invited.pk}/enlace/").status_code == 403
    invited.refresh_from_db()
    assert invited.invite_nonce == ""


def test_link_view_is_post_only(admin_person, invited, client_for):
    assert (
        client_for(admin_person.login).get(f"/equipo/personas/{invited.pk}/enlace/").status_code
        == 405
    )


def test_link_action_is_audited_without_the_token(admin_person, invited, client_for):
    from apps.community.models import ModerationLog

    client_for(admin_person.login).post(f"/equipo/personas/{invited.pk}/enlace/")
    entry = ModerationLog.objects.get(action="signup_link")
    assert entry.actor == admin_person and entry.object_id == invited.pk
    assert "registro" not in entry.summary


def test_lead_sees_people_list_but_no_link_buttons(lead, invited, client_for):
    page = client_for(lead.login).get("/equipo/personas/")
    assert page.status_code == 200
    html = page.content.decode()
    assert "Copiar enlace de registro" not in html and "Agregar personas" not in html


def test_admin_sees_link_buttons(admin_person, invited, client_for):
    html = client_for(admin_person.login).get("/equipo/personas/").content.decode()
    assert "Copiar enlace de registro" in html and "Agregar personas" in html


def test_add_people_is_admin_only(lead, admin_person, client_for):
    assert client_for(lead.login).get("/equipo/personas/agregar/").status_code == 403
    assert (
        client_for(lead.login).post("/equipo/personas/agregar/", {"csv": "a@b.cl"}).status_code
        == 403
    )
    assert client_for(admin_person.login).get("/equipo/personas/agregar/").status_code == 200
    assert not Person.objects.filter(login="a@b.cl").exists()


def test_import_service_refuses_non_admins(lead, make_person):
    report = onboarding.import_team("nuevo@empresa.cl", by=lead)
    assert report.fatal and not Person.objects.filter(login="nuevo@empresa.cl").exists()


def test_role_change_stays_admin_only(lead, member, client_for):
    client_for(lead.login).post(f"/equipo/personas/{member.pk}/", {"role": "lead"})
    member.refresh_from_db()
    member.__dict__.pop("role", None)
    assert member.role == "member"


# --- registro -------------------------------------------------------------------------------------------


def signup_url(person):
    return f"/registro/{services.issue_signup_token(person)}/"


def test_signup_page_shows_email_read_only(invited):
    response = anon().get(signup_url(invited))
    html = response.content.decode()
    assert response.status_code == 200
    assert invited.login in html and "readonly" in html
    # same-origin: no filtra el enlace a otros sitios, pero deja que el navegador mande un Origin válido
    assert response["Referrer-Policy"] == "same-origin"
    assert "no-store" in response["Cache-Control"]


def test_signup_sets_password_logs_in_and_redirects_home(invited):
    c = anon()
    url = signup_url(invited)
    response = c.post(
        url,
        {
            "display_name": "Nueva Persona",
            "password1": GOOD,
            "password2": GOOD,
            "character_class": "architect",
        },
    )
    assert response.status_code == 302 and response.url == "/"
    invited.refresh_from_db()
    assert invited.check_password(GOOD) and invited.display_name == "Nueva Persona"
    assert invited.character_class == "architect" and invited.invite_nonce == ""
    assert session_person_id(c) == str(invited.pk)
    assert c.get("/").status_code == 200  # sigue dentro sin encabezado de Tailscale
    assert (
        anon().post(url, {"display_name": "X", "password1": GOOD, "password2": GOOD}).status_code
        == 400
    )


def test_signup_career_is_optional(invited):
    c = anon()
    response = c.post(
        signup_url(invited), {"display_name": "N", "password1": GOOD, "password2": GOOD}
    )
    assert response.status_code == 302
    invited.refresh_from_db()
    assert invited.character_class == ""


def test_signup_rejects_mismatch_weak_and_bad_career(invited):
    c = anon()
    url = signup_url(invited)
    cases = [
        {"display_name": "N", "password1": GOOD, "password2": GOOD + "x"},
        {"display_name": "N", "password1": "12345678", "password2": "12345678"},
        {"display_name": "N", "password1": "qwertyuiop", "password2": "qwertyuiop"},
        {"display_name": "N", "password1": "nueva@empresa.cl", "password2": "nueva@empresa.cl"},
        {"display_name": "", "password1": GOOD, "password2": GOOD},
        {"display_name": "N", "password1": GOOD, "password2": GOOD, "character_class": "dios"},
    ]
    for data in cases:
        response = c.post(url, data)
        assert response.status_code == 200, data
        invited.refresh_from_db()
        assert not invited.has_usable_password(), data
        assert session_person_id(c) is None
    assert c.post(url, cases[0] | {"password2": GOOD}).status_code == 302  # el enlace sigue vivo


@pytest.mark.parametrize("kind", ["garbage", "expired", "used", "tampered", "replaced"])
def test_invalid_links_give_the_same_friendly_page(invited, kind, monkeypatch):
    token = services.issue_signup_token(invited)
    if kind == "garbage":
        token = "no-es-un-token"
    elif kind == "tampered":
        token = token[:-2] + "zz"
    elif kind == "replaced":
        services.issue_signup_token(invited)
    elif kind == "used":
        services.complete_signup(invited, display_name="N", password=GOOD)
    elif kind == "expired":
        import time

        monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: time.time() + 8 * 86400))
    response = anon().get(f"/registro/{token}/")
    html = response.content.decode()
    assert response.status_code == 400
    assert "administrador" in html and "nueva@empresa.cl" not in html
    assert "<form" not in html.split("<main")[1].split("</main>")[0].replace("theme", "")


def test_invalid_pages_are_identical_for_every_failure(invited):
    token = services.issue_signup_token(invited)
    services.complete_signup(invited, display_name="N", password=GOOD)
    bodies = {anon().get(f"/registro/{t}/").content for t in (token, "x", "a.b.c:d:e")}
    assert len({b.replace(b"csrfmiddlewaretoken", b"") for b in bodies}) == 1


def test_signup_needs_csrf(invited):
    c = anon(enforce_csrf_checks=True)
    response = c.post(
        signup_url(invited), {"display_name": "N", "password1": GOOD, "password2": GOOD}
    )
    assert response.status_code == 403


def test_password_reset_for_a_person_who_already_has_one(invited):
    set_password(invited, "Vieja-clave-3318#")
    c = anon()
    c.post(signup_url(invited), {"display_name": "N", "password1": GOOD, "password2": GOOD})
    invited.refresh_from_db()
    assert invited.check_password(GOOD) and not invited.check_password("Vieja-clave-3318#")


def test_signup_page_escapes_names(invited):
    invited.display_name = "<script>alert(1)</script>"
    invited.save()
    html = anon().get(signup_url(invited)).content.decode()
    assert "<script>alert(1)</script>" not in html


# --- entrar ---------------------------------------------------------------------------------------------


@pytest.fixture
def with_password(member):
    return set_password(member)


def login(c, email, password, **extra):
    return c.post("/entrar/", {"email": email, "password": password, **extra})


def test_login_ok(with_password):
    c = anon()
    response = login(c, "ANA@lev.cl ", GOOD)
    assert response.status_code == 302 and response.url == "/"
    assert session_person_id(c) == str(with_password.pk)
    assert c.get("/").status_code == 200


def test_login_page_renders(client_for):
    response = anon().get("/entrar/")
    assert response.status_code == 200
    assert 'name="password"' in response.content.decode()


def test_wrong_password_and_unknown_email_are_indistinguishable(with_password):
    a = login(anon(), with_password.login, "mala")
    b = login(anon(), "nadie@lev.cl", "mala")
    assert a.status_code == b.status_code == 200
    for r in (a, b):
        assert "correo o contraseña incorrectos" in r.content.decode().lower()
    strip = lambda r: r.content.split(b"<main")[1].split(b"csrfmiddlewaretoken")[0]  # noqa: E731
    assert strip(a).replace(b"ana@lev.cl", b"") == strip(b).replace(b"nadie@lev.cl", b"")


@pytest.mark.parametrize("status", ["pending", "suspended"])
def test_pending_and_suspended_cannot_log_in(make_person, status):
    person = set_password(make_person("p@lev.cl", status=status))
    c = anon()
    response = login(c, person.login, GOOD)
    assert "correo o contraseña incorrectos" in response.content.decode().lower()
    assert session_person_id(c) is None


def test_inactive_person_cannot_log_in(with_password):
    with_password.is_active = False
    with_password.save()
    assert session_person_id(_logged(anon(), with_password.login)) is None


def _logged(c, email, password=GOOD):
    login(c, email, password)
    return c


def test_person_without_password_cannot_log_in(member):
    for pw in ("", "!", "ana"):
        assert session_person_id(_logged(anon(), member.login, pw)) is None


def test_login_rate_limit_blocks_even_the_right_password(with_password):
    c = anon()
    for _ in range(5):
        login(c, with_password.login, "mala")
    response = login(c, with_password.login, GOOD)
    assert "Demasiados intentos" in response.content.decode()
    assert session_person_id(c) is None


def test_rate_limit_is_per_email(with_password, make_person):
    other = set_password(make_person("otra@lev.cl"))
    for _ in range(5):
        login(anon(), with_password.login, "mala")
    assert session_person_id(_logged(anon(), other.login)) == str(other.pk)


def test_rate_limit_counts_unknown_emails_too():
    c = anon()
    for _ in range(5):
        login(c, "nadie@lev.cl", "x")
    assert "Demasiados intentos" in login(c, "nadie@lev.cl", "x").content.decode()


def test_rate_limit_resets_after_success(with_password):
    c = anon()
    for _ in range(4):
        login(c, with_password.login, "mala")
    assert login(c, with_password.login, GOOD).status_code == 302
    c = anon()
    for _ in range(4):
        login(c, with_password.login, "mala")
    assert login(c, with_password.login, GOOD).status_code == 302


def test_rate_limit_window_is_fifteen_minutes():
    assert services.LOGIN_MAX_FAILURES == 5 and services.LOGIN_WINDOW_SECONDS == 900


EVIL = [
    "//evil.com",
    "/\\evil.com",
    "///evil.com",
    "https://evil.com",
    "http://evil.com/x",
    "javascript:alert(1)",
    "\\\\evil.com",
    "/%5Cevil.com",
]


@pytest.mark.parametrize("target", EVIL)
def test_login_next_cannot_open_redirect(with_password, target):
    for how in ("post", "query"):
        c = anon()
        if how == "post":
            response = login(c, with_password.login, GOOD, next=target)
        else:
            response = c.post(
                "/entrar/?next=" + target, {"email": with_password.login, "password": GOOD}
            )
        assert response.status_code == 302
        assert response.url == "/", (how, target, response.url)


def test_login_next_local_path_is_kept(with_password):
    assert login(anon(), with_password.login, GOOD, next="/rutas/").url == "/rutas/"


def test_login_needs_csrf(with_password):
    c = anon(enforce_csrf_checks=True)
    assert login(c, with_password.login, GOOD).status_code == 403


# --- salir ----------------------------------------------------------------------------------------------


def test_logout_is_post_only_and_clears_session(with_password):
    c = anon()
    login(c, with_password.login, GOOD)
    assert c.get("/salir/").status_code == 405
    assert session_person_id(c) is not None
    response = c.post("/salir/")
    assert response.status_code == 302 and response.url == "/bienvenida/"
    assert session_person_id(c) is None
    assert c.get("/").status_code == 302


def test_logout_needs_csrf(with_password):
    c = anon(enforce_csrf_checks=True)
    assert c.post("/salir/").status_code == 403


# --- bienvenida y acceso anónimo ------------------------------------------------------------------------


def test_welcome_is_public_and_has_the_pitch():
    response = anon().get("/bienvenida/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "Levantamiento Digital 101" in html and "Entrar" in html
    assert "¿Te invitaron?" in html and "¿Olvidaste tu contraseña?" in html
    assert 'action="/entrar/"' in html


def test_anonymous_requests_are_redirected_to_welcome():
    c = anon()
    response = c.get("/rutas/")
    assert response.status_code == 302 and response.url.startswith("/bienvenida/")
    assert "next=%2Frutas%2F" in response.url
    assert c.get("/").status_code == 302
    assert c.post("/foro/", {}).status_code == 302
    assert c.get("/admin/").status_code == 302


def test_healthz_stays_open_for_the_local_proxy():
    assert anon().get("/healthz").status_code == 200


@pytest.mark.parametrize("path", ["/bienvenida/", "/entrar/", "/registro/x/", "/"])
def test_untrusted_addresses_get_403_even_on_public_pages(path):
    assert Client(REMOTE_ADDR="10.9.9.9").get(path).status_code == 403


def test_welcome_for_a_logged_in_person_goes_home(member_client):
    assert member_client.get("/bienvenida/").status_code == 302


def test_welcome_next_hidden_field_is_sanitized():
    html = anon().get("/bienvenida/?next=//evil.com").content.decode()
    assert "evil.com" not in html


def test_public_pages_escape_next():
    html = anon().get('/entrar/?next=/a"><script>alert(1)</script>').content.decode()
    assert "<script>alert(1)</script>" not in html


# --- convivencia con Tailscale -------------------------------------------------------------------------


def test_header_login_still_works_without_a_password(client_for, member):
    c = client_for(member.login)
    assert c.get("/").status_code == 200
    assert not member.has_usable_password()
    assert c.session["_auth_user_backend"].endswith("TailscaleBackend")


def test_header_creates_pending_person_as_before(client_for):
    assert client_for("nuevo@lev.cl").get("/").url == "/espera/"


def test_header_does_not_hijack_a_password_session(client_for, with_password, make_person, caplog):
    other = make_person("jefe2@lev.cl")
    c = anon()
    login(c, with_password.login, GOOD)
    c.defaults["HTTP_TAILSCALE_USER_LOGIN"] = other.login
    with caplog.at_level(logging.WARNING, logger="apps.accounts"):
        response = c.get("/")
    assert response.status_code == 200
    assert session_person_id(c) == str(with_password.pk)
    assert "distinta" in caplog.text
    assert with_password.login not in caplog.text and other.login not in caplog.text


def test_matching_header_keeps_the_password_session(client_for, with_password):
    c = anon()
    login(c, with_password.login, GOOD)
    c.defaults["HTTP_TAILSCALE_USER_LOGIN"] = with_password.login
    c.defaults["HTTP_TAILSCALE_USER_NAME"] = "Ana Tailscale"
    assert c.get("/").status_code == 200
    assert session_person_id(c) == str(with_password.pk)


def test_missing_header_does_not_log_a_password_session_out(with_password):
    c = anon()
    login(c, with_password.login, GOOD)
    for _ in range(2):
        assert c.get("/").status_code == 200


def test_unknown_header_does_not_create_people_over_a_password_session(with_password):
    c = anon()
    login(c, with_password.login, GOOD)
    c.defaults["HTTP_TAILSCALE_USER_LOGIN"] = "intruso@lev.cl"
    c.get("/")
    assert not Person.objects.filter(login="intruso@lev.cl").exists()


def test_login_page_lets_a_header_session_switch_to_password(client_for, member, make_person):
    other = set_password(make_person("b@lev.cl"))
    c = client_for(member.login)
    c.get("/")
    page = c.get("/entrar/")
    assert page.status_code == 200 and "Tailscale" in page.content.decode()
    assert login(c, other.login, GOOD).status_code == 302
    assert session_person_id(c) == str(other.pk)
    assert c.get("/").status_code == 200
    assert session_person_id(c) == str(other.pk)  # el encabezado de member no la desplaza


def test_header_switches_header_sessions_as_before(client_for, make_person):
    make_person("a@lev.cl")
    b = make_person("b@lev.cl")
    c = client_for("a@lev.cl")
    c.get("/")
    c.defaults["HTTP_TAILSCALE_USER_LOGIN"] = "b@lev.cl"
    c.get("/")
    assert session_person_id(c) == str(b.pk)


def test_suspended_password_session_gets_the_suspended_page(with_password):
    c = anon()
    login(c, with_password.login, GOOD)
    services.suspend(with_password)
    response = c.get("/")
    assert response.status_code in (302, 403)


# --- texto de invitación -----------------------------------------------------------------------------------


def test_invitation_text_carries_the_link_and_no_other_secret(invited, settings):
    settings.SECRET_KEY = "super-secreto-de-prueba-123"
    settings.NIM_API_KEY = "nvapi-clave-de-prueba"
    url = services.signup_url(invited)
    text = onboarding.invitation_text(invited, signup_url=url)
    assert url in text and url.startswith("https://") and "/registro/" in url
    assert "super-secreto-de-prueba-123" not in text and "nvapi-clave-de-prueba" not in text
    assert settings.SECRET_KEY not in url
    assert "7 días" in text


def test_invitation_text_without_link_has_no_registration_path(invited):
    assert "/registro/" not in onboarding.invitation_text(invited)
    assert "/registro/" not in onboarding.invitation_text()


# --- comando -----------------------------------------------------------------------------------------------


def run_cmd(*args):
    out = StringIO()
    call_command("enlace_registro", *args, stdout=out)
    return out.getvalue()


def test_command_prints_a_working_link(invited):
    output = run_cmd(invited.login)
    link = next(w for w in output.split() if "/registro/" in w)
    token = link.rstrip("/").rsplit("/", 1)[1]
    assert services.resolve_signup_token(token).pk == invited.pk
    assert link.startswith("https://")


def test_command_refuses_unknown_and_pending(make_person):
    make_person("p@lev.cl", status="pending")
    for email in ("nadie@lev.cl", "p@lev.cl", "no-es-correo"):
        with pytest.raises(CommandError):
            run_cmd(email)


# --- ajustes --------------------------------------------------------------------------------------------------


def test_settings_backends_and_login_url():
    assert settings.AUTHENTICATION_BACKENDS == [
        "apps.accounts.backends.TailscaleBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]
    assert settings.LOGIN_URL == "accounts:welcome"
    assert settings.AUTH_PASSWORD_VALIDATORS
    assert settings.SESSION_COOKIE_HTTPONLY and settings.SESSION_COOKIE_SAMESITE == "Lax"


def test_prod_session_cookies_are_secure(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "x" * 50)
    monkeypatch.setenv("ALLOWED_HOSTS", "a.ts.net")
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    prod = importlib.import_module("config.settings.prod")
    assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE
    assert prod.SESSION_COOKIE_HTTPONLY and prod.SESSION_COOKIE_SAMESITE == "Lax"
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)


def test_tailscale_client_helper_is_unchanged():
    assert tailscale_client("a@b.cl").defaults["HTTP_TAILSCALE_USER_LOGIN"] == "a@b.cl"


def test_person_status_constants():
    assert PersonStatus.APPROVED == "approved"
