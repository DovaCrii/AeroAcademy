"""Enlace de inscripción del equipo (D35): un solo enlace para todos, solo el admin lo genera, vence y se revoca."""

import logging
from datetime import timedelta
from io import StringIO

import pytest
from django.core import signing
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone

from apps.accounts import team_link
from apps.accounts.models import Person, PersonStatus, TeamSignupLink
from apps.notifications.models import Notification
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db

GOOD = "Clave-de-prueba-4417!"  # valor de prueba generado para esta suite


def anon():
    return Client(REMOTE_ADDR="127.0.0.1", enforce_csrf_checks=False)


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def link(admin_person):
    record, token = team_link.create_link(admin_person, days=14)
    record.token = token  # solo para las pruebas: en la base nunca se guarda
    return record


def url_of(token):
    return f"/inscripcion/{token}/"


def data(email="nuevo@empresa.cl", name="Nuevo Nombre", password=GOOD, confirm=None, **extra):
    return {
        "email": email,
        "display_name": name,
        "password1": password,
        "password2": password if confirm is None else confirm,
        **extra,
    }


def session_pid(client):
    return client.session.get("_auth_user_id")


# --- generar y revocar: solo admin --------------------------------------------------------------


def test_admin_generates_and_sees_link_once(admin_person):
    c = tailscale_client(admin_person.login)
    r = c.post("/equipo/personas/enlace-equipo/", {"days": "30"}, follow=True)
    assert r.status_code == 200
    html = r.content.decode()
    assert "/inscripcion/" in html
    record = TeamSignupLink.objects.get()
    assert record.created_by_id == admin_person.pk and record.uses == 0
    assert 29 <= (record.expires_at - record.created_at).days <= 30
    again = c.get("/equipo/personas/")
    assert "/inscripcion/" not in again.content.decode()  # el enlace no se vuelve a mostrar
    assert "Revocar" in again.content.decode()


def test_default_validity_is_14_days(admin_person):
    tailscale_client(admin_person.login).post("/equipo/personas/enlace-equipo/", {})
    record = TeamSignupLink.objects.get()
    assert 13 <= (record.expires_at - record.created_at).days <= 14


@pytest.mark.parametrize("days", ["0", "5", "90", "x", "-7"])
def test_invalid_validity_is_rejected(admin_person, days):
    tailscale_client(admin_person.login).post("/equipo/personas/enlace-equipo/", {"days": days})
    assert not TeamSignupLink.objects.exists()


@pytest.mark.parametrize("who", ["lead", "member"])
def test_only_admin_can_generate_or_revoke(who, lead, member, link):
    person = lead if who == "lead" else member
    c = tailscale_client(person.login)
    assert c.post("/equipo/personas/enlace-equipo/", {"days": "7"}).status_code == 403
    assert c.post("/equipo/personas/enlace-equipo/revocar/").status_code == 403
    assert TeamSignupLink.objects.count() == 1
    assert TeamSignupLink.objects.get().revoked_at is None


def test_card_hidden_from_lead_and_visible_to_admin(lead, admin_person):
    assert "Enlace de inscripción del equipo" not in (
        tailscale_client(lead.login).get("/equipo/personas/").content.decode()
    )
    assert "Enlace de inscripción del equipo" in (
        tailscale_client(admin_person.login).get("/equipo/personas/").content.decode()
    )


def test_generate_and_revoke_are_post_only(admin_person):
    c = tailscale_client(admin_person.login)
    assert c.get("/equipo/personas/enlace-equipo/").status_code == 405
    assert c.get("/equipo/personas/enlace-equipo/revocar/").status_code == 405


def test_generate_requires_csrf(admin_person):
    c = Client(
        REMOTE_ADDR="127.0.0.1",
        HTTP_TAILSCALE_USER_LOGIN=admin_person.login,
        enforce_csrf_checks=True,
    )
    assert c.post("/equipo/personas/enlace-equipo/", {"days": "7"}).status_code == 403
    assert not TeamSignupLink.objects.exists()


def test_admin_revokes(admin_person, link):
    token = link.token
    tailscale_client(admin_person.login).post("/equipo/personas/enlace-equipo/revocar/")
    assert TeamSignupLink.objects.get().revoked_at is not None
    assert anon().get(url_of(token)).status_code == 400


def test_regenerating_revokes_the_previous_one(admin_person):
    first, first_token = team_link.create_link(admin_person, days=7)
    second, second_token = team_link.create_link(admin_person, days=14)
    first.refresh_from_db()
    assert first.revoked_at is not None and second.revoked_at is None
    assert anon().get(url_of(first_token)).status_code == 400
    assert anon().get(url_of(second_token)).status_code == 200


def test_only_hash_is_stored(link):
    token = link.token
    secret = token.split(":")[0].split(".", 1)[1]
    row = TeamSignupLink.objects.get()
    assert secret not in row.secret_hash and secret not in str(row.__dict__.values())
    assert len(row.secret_hash) == 64


def test_admin_generate_is_logged_without_the_link(admin_person):
    from apps.community.models import ModerationLog

    c = tailscale_client(admin_person.login)
    c.post("/equipo/personas/enlace-equipo/", {"days": "7"})
    entry = ModerationLog.objects.get(action="team_link")
    assert "/inscripcion/" not in entry.summary and ":" not in entry.summary
    assert entry.actor_id == admin_person.pk


# --- token: vencido, revocado, manipulado ---------------------------------------------------------


def test_valid_token_shows_form(link):
    r = anon().get(url_of(link.token))
    assert r.status_code == 200
    html = r.content.decode()
    assert 'name="email"' in html and 'name="password1"' in html
    assert "no-store" in r["Cache-Control"] and r["Referrer-Policy"] == "same-origin"


def test_expired_token_is_rejected(link, monkeypatch):
    token = link.token
    real = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: real + timedelta(days=14, minutes=-1))
    assert anon().get(url_of(token)).status_code == 200
    monkeypatch.setattr(timezone, "now", lambda: real + timedelta(days=14, minutes=1))
    r = anon().get(url_of(token))
    assert r.status_code == 400 and "enlace nuevo" in r.content.decode()


def test_expired_record_rejects_even_with_valid_signature(link):
    TeamSignupLink.objects.update(expires_at=link.created_at)
    assert anon().get(url_of(link.token)).status_code == 400
    r = anon().post(url_of(link.token), data())
    assert r.status_code == 400 and not Person.objects.filter(login="nuevo@empresa.cl").exists()


def test_tampered_tokens_are_rejected(link):
    token = link.token
    flipped = token[:-1] + ("A" if token[-1] != "A" else "B")
    bad_secret = token.replace(".", ".0", 1)
    for bad in (flipped, bad_secret, "x", "a.b:c:d", token.split(":")[0], "1.2:3:4"):
        assert anon().get(url_of(bad)).status_code == 400, bad
        assert anon().post(url_of(bad), data()).status_code == 400
    assert not Person.objects.filter(login="nuevo@empresa.cl").exists()


def test_token_signed_with_other_salt_is_rejected(link):
    row = TeamSignupLink.objects.get()
    forged = signing.TimestampSigner(salt="otra.sal").sign(f"{row.pk}.{'a' * 32}")
    assert anon().get(url_of(forged)).status_code == 400


def test_token_cannot_point_to_a_foreign_row(admin_person):
    first, token = team_link.create_link(admin_person, days=7)
    secret = token.split(":")[0].split(".", 1)[1]
    other = TeamSignupLink.objects.create(
        secret_hash="0" * 64, expires_at=first.expires_at, created_by=admin_person
    )
    forged = signing.TimestampSigner(salt=team_link.SALT).sign(f"{other.pk}.{secret}")
    assert anon().get(url_of(forged)).status_code == 400


# --- inscripción ------------------------------------------------------------------------------------


def test_preapproved_without_password_sets_password_and_logs_in(link, make_person):
    person = make_person("ana.nueva@empresa.cl")
    assert not person.has_usable_password()
    c = anon()
    r = c.post(
        url_of(link.token),
        data("  Ana.Nueva@Empresa.CL ", "Ana Nueva", character_class="pilot"),
    )
    assert r.status_code == 302 and r.url == "/"
    person.refresh_from_db()
    assert person.check_password(GOOD) and person.display_name == "Ana Nueva"
    assert person.character_class == "pilot"
    assert session_pid(c) == str(person.pk)
    assert Person.objects.filter(login="ana.nueva@empresa.cl").count() == 1
    assert TeamSignupLink.objects.get().uses == 1
    assert c.get("/").status_code == 200  # ya está dentro (Primeros pasos)


def test_link_is_reusable_by_many(link, make_person):
    make_person("uno@empresa.cl")
    make_person("dos@empresa.cl")
    token = link.token
    assert anon().post(url_of(token), data("uno@empresa.cl")).status_code == 302
    assert anon().post(url_of(token), data("dos@empresa.cl")).status_code == 302
    assert TeamSignupLink.objects.get().uses == 2


def test_unknown_email_creates_pending_notifies_admins_and_cannot_log_in(
    link, admin_person, lead, member
):
    c = anon()
    r = c.post(url_of(link.token), data("Recien@Empresa.cl", "Recién Llegado"))
    assert r.status_code == 200
    assert "administrador aprobará" in r.content.decode()
    assert session_pid(c) is None
    person = Person.objects.get(login="recien@empresa.cl")
    assert person.status == PersonStatus.PENDING and person.check_password(GOOD)
    assert person.role == "member" and not person.is_staff and not person.is_superuser
    assert person.display_name == "Recién Llegado"
    # avisos a responsables/admin, sin contraseña
    notes = Notification.objects.filter(kind="person_pending")
    assert {n.recipient_id for n in notes} >= {admin_person.pk, lead.pk}
    assert not Notification.objects.filter(recipient=member, kind="person_pending").exists()
    for n in notes:
        assert GOOD not in n.title + n.body + n.url
    # no entra por /entrar/ mientras esté pendiente
    login = anon().post("/entrar/", {"email": "recien@empresa.cl", "password": GOOD})
    assert login.status_code == 200 and "incorrectos" in login.content.decode()
    # ... y sí después de aprobada
    from apps.accounts import services

    services.approve(person, by=admin_person)
    c2 = anon()
    assert c2.post("/entrar/", {"email": "recien@empresa.cl", "password": GOOD}).status_code == 302
    assert session_pid(c2) == str(person.pk)
    assert TeamSignupLink.objects.get().uses == 1


def test_pending_without_password_gets_password_and_stays_pending(link, make_person):
    person = make_person("pend@empresa.cl", status="pending")
    c = anon()
    r = c.post(url_of(link.token), data("pend@empresa.cl"))
    assert r.status_code == 200 and session_pid(c) is None
    person.refresh_from_db()
    assert person.status == PersonStatus.PENDING and person.check_password(GOOD)


def test_existing_password_does_not_log_in_nor_change_password(link, make_person):
    person = make_person("tiene@empresa.cl")
    person.set_password("Otra-clave-vieja-882!")
    person.save()
    old_hash = Person.objects.get(pk=person.pk).password
    c = anon()
    r = c.post(url_of(link.token), data("tiene@empresa.cl"))
    html = r.content.decode()
    assert r.status_code == 200 and "Ese correo ya tiene cuenta" in html and "/entrar/" in html
    assert session_pid(c) is None
    assert Person.objects.get(pk=person.pk).password == old_hash
    assert TeamSignupLink.objects.get().uses == 0


def test_suspended_is_refused_generically(link, make_person):
    person = make_person("susp@empresa.cl", status="suspended")
    c = anon()
    r = c.post(url_of(link.token), data("susp@empresa.cl"))
    assert r.status_code == 200 and session_pid(c) is None
    person.refresh_from_db()
    assert not person.has_usable_password() and person.status == PersonStatus.SUSPENDED
    assert "Ese correo ya tiene cuenta" not in r.content.decode()


def test_inactive_is_refused(link, make_person):
    person = make_person("baja@empresa.cl")
    person.is_active = False
    person.save()
    c = anon()
    c.post(url_of(link.token), data("baja@empresa.cl"))
    person.refresh_from_db()
    assert session_pid(c) is None and not person.has_usable_password()


@pytest.mark.parametrize("role", ["lead", "admin"])
def test_privileged_accounts_cannot_be_claimed_with_the_team_link(link, make_person, role):
    person = make_person(f"{role}x@empresa.cl", role=role)
    c = anon()
    r = c.post(url_of(link.token), data(f"{role}x@empresa.cl"))
    person.refresh_from_db()
    assert r.status_code == 200 and session_pid(c) is None
    assert not person.has_usable_password()
    assert "enlace personal" in r.content.decode()


def test_bootstrap_admin_login_cannot_be_claimed(link, settings):
    settings.BOOTSTRAP_ADMINS = ["root@empresa.cl"]
    c = anon()
    c.post(url_of(link.token), data("root@empresa.cl"))
    assert session_pid(c) is None
    assert not Person.objects.filter(login="root@empresa.cl").exists()


@pytest.mark.parametrize(
    "bad",
    [
        data("no-es-correo"),
        data(""),
        data("a@b"),
        data("x" * 250 + "@e.cl"),
        data(confirm="otra-cosa-distinta"),
        data(password="corta1"),
        data(password="1234567890123"),
        data(password="password1234"),
        data(name=""),
        data(character_class="mago"),
    ],
)
def test_invalid_submissions_create_nothing(link, bad):
    c = anon()
    r = c.post(url_of(link.token), bad)
    assert r.status_code == 200 and session_pid(c) is None
    assert not Person.objects.filter(status="pending").exists()
    assert TeamSignupLink.objects.get().uses == 0


def test_password_similar_to_email_is_rejected(link):
    r = anon().post(url_of(link.token), data("clavesecreta@empresa.cl", password="clavesecreta"))
    assert not Person.objects.filter(login="clavesecreta@empresa.cl").exists()
    assert r.status_code == 200


def test_script_in_name_is_escaped_everywhere(link, admin_person):
    token = link.token
    r = anon().post(url_of(token), data("xss@empresa.cl", "<script>alert(1)</script>"))
    assert b"<script>alert(1)" not in r.content
    page = tailscale_client(admin_person.login).get("/moderacion/")
    assert b"<script>alert(1)" not in page.content
    bad = anon().post(url_of(token), data("<script>x</script>@e.cl", "N"))
    assert b"<script>x" not in bad.content


def test_already_logged_in_visitor_keeps_working(link, member):
    r = tailscale_client(member.login).get(url_of(link.token))
    assert r.status_code == 200


# --- límite de envíos ---------------------------------------------------------------------------------


def test_rate_limit_per_ip_and_link(link, admin_person):
    token = link.token
    c = anon()
    for _ in range(team_link.MAX_SUBMISSIONS):
        assert c.post(url_of(token), data("mala@empresa.cl", confirm="distinta")).status_code == 200
    r = c.post(url_of(token), data("buena@empresa.cl"))
    assert r.status_code == 429 and "Demasiados intentos" in r.content.decode()
    assert not Person.objects.filter(login="buena@empresa.cl").exists()
    # otra IP no se ve afectada
    other = Client(REMOTE_ADDR="127.0.0.1")
    other.defaults["REMOTE_ADDR"] = "::1"
    assert other.post(url_of(token), data("buena@empresa.cl")).status_code == 200


def test_rate_limit_does_not_count_get(link):
    token = link.token
    c = anon()
    for _ in range(team_link.MAX_SUBMISSIONS + 3):
        assert c.get(url_of(token)).status_code == 200


# --- CSRF, redirecciones y registros --------------------------------------------------------------


def test_signup_requires_csrf(link):
    c = Client(REMOTE_ADDR="127.0.0.1", enforce_csrf_checks=True)
    r = c.post(url_of(link.token), data())
    assert r.status_code == 403 and not Person.objects.filter(login="nuevo@empresa.cl").exists()
    assert "csrfmiddlewaretoken" in c.get(url_of(link.token)).content.decode()


@pytest.mark.parametrize("nxt", ["//evil.com", "/\\evil.com", "https://evil.com/", "javascript:1"])
def test_no_open_redirect(link, make_person, nxt):
    make_person("redir@empresa.cl")
    token = link.token
    r = anon().post(url_of(token) + "?next=" + nxt, data("redir@empresa.cl", next=nxt))
    assert r.status_code == 302 and r.url == "/"


def test_no_password_in_logs_or_responses(link, make_person, caplog):
    make_person("log@empresa.cl")
    token = link.token
    with caplog.at_level(logging.DEBUG):
        r1 = anon().post(url_of(token), data("log@empresa.cl"))
        r2 = anon().post(url_of(token), data("otro@empresa.cl", confirm="distinta-xx"))
        r3 = anon().post(url_of(token), data("nuevo2@empresa.cl"))
    assert GOOD not in caplog.text and token not in caplog.text
    for r in (r1, r2, r3):
        assert GOOD not in r.content.decode()


def test_public_without_header_does_not_redirect_to_welcome(link):
    r = anon().get(url_of(link.token))
    assert r.status_code == 200


def test_foreign_ip_is_forbidden(link):
    c = Client(REMOTE_ADDR="10.0.0.9")
    assert c.get(url_of(link.token)).status_code == 403


# --- bienvenida --------------------------------------------------------------------------------------


def test_welcome_copy_stays_accurate(link):
    html = anon().get("/bienvenida/").content.decode()
    assert "¿Te invitaron?" in html and "el enlace que te mandó el admin" in html
    assert "/inscripcion/" not in html


# --- comando de la VM ---------------------------------------------------------------------------------


def run(*args):
    out = StringIO()
    call_command("enlace_equipo", *args, stdout=out)
    return out.getvalue()


def test_command_generates_link_and_revokes():
    out = run("--dias", "7")
    assert "/inscripcion/" in out
    row = TeamSignupLink.objects.get()
    assert row.created_by is None and 6 <= (row.expires_at - row.created_at).days <= 7
    token = out.split("/inscripcion/")[1].split("/")[0]
    assert anon().get(url_of(token)).status_code == 200
    run("--revocar")
    assert TeamSignupLink.objects.get().revoked_at is not None
    assert anon().get(url_of(token)).status_code == 400


def test_command_default_days_and_validation():
    run()
    row = TeamSignupLink.objects.get()
    assert 13 <= (row.expires_at - row.created_at).days <= 14
    with pytest.raises(CommandError):
        run("--dias", "3")


def test_command_revoke_without_active_link_is_harmless():
    assert "No hay" in run("--revocar")
