import pytest
from django.contrib.auth.models import Group
from django.test import override_settings

from apps.accounts import services
from apps.accounts.models import Person, PersonStatus

pytestmark = pytest.mark.django_db


# --- encabezado de Tailscale ------------------------------------------------------------------


def test_header_from_trusted_proxy_creates_pending_person(client_for):
    response = client_for("nueva@lev.cl", name="Nueva Persona", pic="https://x.test/a.png").get("/")
    person = Person.objects.get(login="nueva@lev.cl")
    assert person.status == PersonStatus.PENDING
    assert person.display_name == "Nueva Persona"
    assert person.avatar_url == "https://x.test/a.png"
    assert person.role == "member"
    assert not person.has_usable_password()
    assert response.status_code == 302 and response.url == "/espera/"


def test_header_updates_existing_person(client_for, member):
    client_for(member.login, name="Ana Nueva", pic="https://x.test/b.png").get("/")
    member.refresh_from_db()
    assert member.display_name == "Ana Nueva"
    assert member.avatar_url == "https://x.test/b.png"
    assert Person.objects.count() == 1


def test_existing_role_survives_a_new_session(client_for, lead, admin_person):
    """Regresión: Django 5.2 llama a configure_user en cada autenticación."""
    for person, role in ((lead, "lead"), (admin_person, "admin")):
        client_for(person.login).get("/")
        person.refresh_from_db()
        person.__dict__.pop("role", None)
        assert person.role == role
        assert person.status == PersonStatus.APPROVED


def test_login_is_normalized(client_for, member):
    client_for(member.login.upper()).get("/")
    assert Person.objects.count() == 1


def test_header_from_other_ip_is_403_and_creates_nobody(client_for):
    response = client_for("intruso@evil.test", remote_addr="10.0.0.5").get("/")
    assert response.status_code == 403
    assert not Person.objects.exists()


def test_other_ip_without_header_is_403(client_for):
    assert client_for("", remote_addr="192.168.1.20").get("/").status_code == 403


def test_missing_header_goes_to_welcome(client_for):
    response = client_for("").get("/")
    assert response.status_code == 302 and response.url.startswith("/bienvenida/")


@pytest.mark.parametrize("addr", ["::1", "::ffff:127.0.0.1"])
def test_ipv6_loopback_and_mapped_are_trusted(client_for, addr, member):
    assert client_for(member.login, remote_addr=addr).get("/").status_code == 200


def test_invalid_remote_addr_is_403(client_for, member):
    assert client_for(member.login, remote_addr="no-es-ip").get("/").status_code == 403


def test_other_identity_in_same_session_switches_person(client_for, make_person):
    make_person("a@lev.cl")
    make_person("b@lev.cl")
    client = client_for("a@lev.cl")
    client.get("/")
    client.defaults["HTTP_TAILSCALE_USER_LOGIN"] = "b@lev.cl"
    response = client.get("/")
    assert response.status_code == 200
    assert str(client.session["_auth_user_id"]) == str(Person.objects.get(login="b@lev.cl").pk)


# --- DEV_REMOTE_USER ----------------------------------------------------------------------------


@override_settings(DEBUG=False, DEV_REMOTE_USER="dev@lev.cl")
def test_dev_remote_user_is_ignored_when_debug_is_false(client_for):
    assert client_for("").get("/").status_code == 302  # a la bienvenida, sin identidad
    assert not Person.objects.exists()


@override_settings(DEBUG=True, DEV_REMOTE_USER="dev@lev.cl")
def test_dev_remote_user_works_in_debug(client_for):
    response = client_for("").get("/")
    assert response.status_code == 302
    assert Person.objects.filter(login="dev@lev.cl").exists()


@override_settings(DEBUG=True, DEV_REMOTE_USER="dev@lev.cl")
def test_dev_remote_user_does_not_bypass_untrusted_ip(client_for):
    assert client_for("", remote_addr="10.1.1.1").get("/").status_code == 403


def test_prod_settings_blank_dev_remote_user(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("SECRET_KEY", "x" * 50)
    monkeypatch.setenv("ALLOWED_HOSTS", "a.ts.net")
    monkeypatch.setenv("DEV_REMOTE_USER", "dev@lev.cl")
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    prod = importlib.import_module("config.settings.prod")
    assert prod.DEV_REMOTE_USER == ""
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)


# --- aprobación -----------------------------------------------------------------------------------


def test_pending_sees_no_content_and_is_sent_to_waiting(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    client = client_for(pending.login)
    for path in ("/", "/admin/", "/cualquier-cosa/"):
        response = client.get(path)
        assert response.status_code == 302 and response.url == "/espera/", path


def test_waiting_page_for_pending(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    response = client_for(pending.login).get("/espera/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "Esperando aprobación" in html
    assert "Academia LEV Digital 101" not in html.split("<main")[0].split("<title>")[0]


def test_approved_on_waiting_goes_home(member_client):
    response = member_client.get("/espera/")
    assert response.status_code == 302 and response.url == "/"


def test_approved_sees_home(member_client):
    response = member_client.get("/")
    assert response.status_code == 200
    assert "Academia LEV Digital 101" in response.content.decode()


def test_suspended_gets_403(client_for, make_person):
    person = make_person("s@lev.cl", status="suspended")
    client = client_for(person.login)
    for path in ("/", "/espera/"):
        response = client.get(path)
        assert response.status_code == 403
        assert "Acceso suspendido" in response.content.decode()


def test_inactive_person_is_403(client_for, member):
    member.is_active = False
    member.save()
    assert client_for(member.login).get("/").status_code == 403


def test_approve_and_suspend_services(make_person, admin_person):
    pending = make_person("p@lev.cl", status="pending")
    services.approve(pending, by=admin_person)
    pending.refresh_from_db()
    assert pending.status == PersonStatus.APPROVED
    assert pending.approved_by == admin_person and pending.approved_at
    services.suspend(pending)
    pending.refresh_from_db()
    assert pending.status == PersonStatus.SUSPENDED


# --- BOOTSTRAP_ADMINS -----------------------------------------------------------------------------


@override_settings(BOOTSTRAP_ADMINS=["jefe@lev.cl"])
def test_bootstrap_admin_enters_approved_and_admin(client_for):
    response = client_for("Jefe@LEV.cl", name="El Jefe").get("/")
    person = Person.objects.get(login="jefe@lev.cl")
    assert response.status_code == 200
    assert person.status == PersonStatus.APPROVED
    assert person.role == "admin"
    assert person.is_staff and person.is_superuser and person.is_lead


@override_settings(BOOTSTRAP_ADMINS=["luis@lev.cl"])
def test_bootstrap_applies_to_existing_person(client_for, make_person):
    existing = make_person("luis@lev.cl", status="pending")
    client_for(existing.login).get("/")
    existing.refresh_from_db()
    assert existing.status == PersonStatus.APPROVED and existing.role == "admin"


def test_non_bootstrap_does_not_become_admin(client_for):
    client_for("otra@lev.cl").get("/")
    person = Person.objects.get(login="otra@lev.cl")
    assert person.role == "member" and not person.is_staff


@override_settings(BOOTSTRAP_ADMINS=["jefe@lev.cl"])
def test_admin_site_only_for_admin(client_for, member):
    admin_response = client_for("jefe@lev.cl").get("/admin/")
    member_response = client_for(member.login).get("/admin/")
    assert admin_response.status_code == 200
    assert member_response.status_code == 302 and "/admin/login" in member_response.url


# --- roles ----------------------------------------------------------------------------------------


def test_role_groups_exist():
    assert set(Group.objects.values_list("name", flat=True)) >= {"member", "lead", "admin"}


def test_set_role_is_exclusive_and_syncs_flags(make_person):
    person = make_person("r@lev.cl")
    assert person.role == "member" and not person.is_lead
    services.set_role(person, "lead")
    assert person.role == "lead" and person.is_lead and not person.is_admin and not person.is_staff
    assert list(person.groups.values_list("name", flat=True)) == ["lead"]
    services.set_role(person, "admin")
    assert person.is_admin and person.is_staff and person.is_superuser
    services.set_role(person, "member")
    assert not person.is_staff and not person.is_superuser
    assert list(person.groups.values_list("name", flat=True)) == ["member"]


def test_set_role_rejects_unknown_role(member):
    with pytest.raises(ValueError):
        services.set_role(member, "dios")


def test_create_superuser_is_approved_admin():
    person = Person.objects.create_superuser("root@lev.cl")
    assert person.is_admin and person.status == PersonStatus.APPROVED


# --- limpieza de datos de entrada -----------------------------------------------------------------


def test_decode_header_value_variants():
    assert services.decode_header_value("=?utf-8?q?Mu=C3=B1oz?=") == "Muñoz"
    assert services.decode_header_value("Muñoz".encode().decode("latin-1")) == "Muñoz"
    assert services.decode_header_value("  Ana  ") == "Ana"
    assert services.decode_header_value("") == ""


@pytest.mark.parametrize(
    "bad", ["javascript:alert(1)", "data:text/html,x", "/relativa.png", "x" * 600]
)
def test_unsafe_avatar_urls_are_dropped(client_for, bad):
    client_for("av@lev.cl", pic=bad).get("/")
    assert Person.objects.get(login="av@lev.cl").avatar_url == ""


def test_long_display_name_is_truncated(client_for):
    client_for("n@lev.cl", name="N" * 400).get("/")
    assert len(Person.objects.get(login="n@lev.cl").display_name) == 150
