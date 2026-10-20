"""Centro de administración (D42), P0-2: cuentas, estado en palabras y acciones (aprobar, rol, suspender, enlaces)."""

import re
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import services, team_link
from apps.accounts.models import Person, TeamSignupLink, TotpDevice
from apps.catalog.models import Discipline
from apps.community.models import ModerationLog
from apps.core import admin_center
from apps.team.models import TeamMember
from tests.conftest import own_queries, tailscale_client

pytestmark = pytest.mark.django_db
URL = "/administracion/cuentas/"


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    cache.clear()
    monkeypatch.setattr(
        admin_center, "public_door_up", lambda: False
    )  # sin sonda de red en estas pruebas
    yield
    cache.clear()


def body(response):
    return response.content.decode().split("<main")[1]


def get(person, path=URL, **params):
    return tailscale_client(person.login).get(path, params)


def post(person, path, data=None):
    return tailscale_client(person.login).post(path, data or {})


def logins_in(html):
    return set(re.findall(r"<small>([^<]+@[^<]+)</small>", html))


def raw(login, status="approved", role=None, **fields):
    """Persona sin pasar por `set_role` (para poder dejarla sin rol)."""
    person = Person.objects.create_user(login, **fields)
    person.status = status
    person.save(update_fields=["status"])
    if role:
        services.set_role(person, role)
    return person


@pytest.fixture
def world(admin_person, make_person):
    """Una persona de cada estado."""
    now = timezone.now()
    people = {
        "pending": make_person("pendiente@example.com", status="pending"),
        "active": make_person("activa@example.com"),
        "never": make_person("nunca@example.com"),
        "suspended": make_person("suspendida@example.com", status="suspended"),
        "norole": raw("sinrol@example.com", last_login=now),
        "lead": make_person("responsable@example.com", role="lead"),
    }
    for key in ("active", "lead"):
        people[key].last_login = now
        people[key].save(update_fields=["last_login"])
    return people


# --- acceso a la página y a las acciones -------------------------------------------------------------------------


def test_only_the_admin_enters_the_accounts_page(admin_person, lead, member):
    assert get(admin_person).status_code == 200
    assert get(lead).status_code == 404  # Q1: cuentas son solo del admin
    assert get(member).status_code == 404


ACTIONS = ("aprobar", "rechazar", "rol", "suspender", "reactivar", "enlace")


@pytest.mark.parametrize("action", ACTIONS)
def test_every_action_is_post_only_and_hidden_from_everyone_else(
    action, admin_person, lead, member, world
):
    url = f"{URL}{world['active'].pk}/{action}/"
    assert get(admin_person, url).status_code == 405
    assert get(lead, url).status_code == 404 and post(lead, url).status_code == 404
    assert get(member, url).status_code == 404 and post(member, url).status_code == 404
    anon = Client(REMOTE_ADDR="127.0.0.1")
    assert anon.post(url).status_code == 302  # a /bienvenida/ como cualquier página protegida


@pytest.mark.parametrize("action", ["aprobar", "suspender", "enlace"])
def test_actions_demand_the_csrf_token(action, admin_person, world):
    client = Client(
        REMOTE_ADDR="127.0.0.1",
        HTTP_TAILSCALE_USER_LOGIN=admin_person.login,
        enforce_csrf_checks=True,
    )
    response = client.post(f"{URL}{world['pending'].pk}/{action}/")
    assert response.status_code == 403
    world["pending"].refresh_from_db()
    assert world["pending"].status == "pending"


# --- filtros ----------------------------------------------------------------------------------------------------


def test_filters_return_exactly_those_people(admin_person, world):
    expect = {
        "pendiente": {"pendiente@example.com"},
        "suspendida": {"suspendida@example.com"},
        # la admin ya entró: esta misma petición registra su entrada
        "nunca": {"nunca@example.com"},
        "activa": {
            "activa@example.com",
            "responsable@example.com",
            "sinrol@example.com",
            admin_person.login,
        },
        "sin-rol": {"sinrol@example.com"},
        "sin-disciplina": {
            "activa@example.com",
            "nunca@example.com",
            "responsable@example.com",
            "sinrol@example.com",
            admin_person.login,
        },
    }
    for estado, logins in expect.items():
        assert logins_in(body(get(admin_person, estado=estado))) == logins, estado
    everyone = logins_in(body(get(admin_person)))
    assert {p.login for p in world.values()} | {admin_person.login} == everyone


def test_the_suspended_are_listed_here_unlike_the_roster(admin_person, world):
    assert "suspendida@example.com" in get(admin_person).content.decode()
    roster = tailscale_client(admin_person.login).get("/equipo/personas/").content.decode()
    assert "suspendida@example.com" not in roster


def test_search_by_name_or_email_and_unknown_filter_is_ignored(admin_person, world):
    world["active"].display_name = "Marta Soto"
    world["active"].save(update_fields=["display_name"])
    assert logins_in(body(get(admin_person, q="marta"))) == {"activa@example.com"}
    assert logins_in(body(get(admin_person, q="responsable@"))) == {"responsable@example.com"}
    assert get(admin_person, estado="no-existe").status_code == 200
    assert get(admin_person, q="x" * 500).status_code == 200


def test_counters_and_filter_chips(admin_person, world):
    counts = admin_center.people_counts()
    assert counts["pending"] == 1 and counts["suspended"] == 1 and counts["no_role"] == 1
    assert counts["never"] == 2 and counts["active"] == 3 and counts["total"] == 7
    html = body(get(admin_person))
    assert "Pendientes <b>1</b>" in html and "Sin rol <b>1</b>" in html
    assert "Sin disciplina <b>" in html and "Desactivadas" not in html
    off = world["active"]
    off.is_active = False
    off.save(update_fields=["is_active"])
    page = body(get(admin_person, estado="desactivada"))
    assert "Desactivadas <b>1</b>" in page and logins_in(page) == {off.login}
    assert "Cuenta desactivada en la administración técnica." in page


def test_pending_come_first_and_suspended_last(admin_person, world):
    html = body(get(admin_person))
    order = [m for m in re.findall(r"<small>([^<]+@[^<]+)</small>", html)]
    assert order[0] == "pendiente@example.com" and order[-1] == "suspendida@example.com"


# --- el estado en una frase -----------------------------------------------------------------------------------------


def test_sentences_for_each_case(world, admin_person):
    now = timezone.now()
    sentence = admin_center.account_sentence
    pending = world["pending"]
    pending.created_at = now - timedelta(days=2)
    assert "Pidió acceso hace 2 días" in sentence(pending, now)
    assert "apruébala o recházala" in sentence(pending, now)
    assert sentence(world["suspended"], now) == "Sin acceso. Sus datos y certificados se conservan."
    never = world["never"]
    assert "Necesita Tailscale o un enlace personal" in sentence(never, now)
    never.set_password("Clave-de-prueba-9271!")
    assert sentence(never, now) == "Aprobada y con contraseña, pero aún no entra."
    active = world["active"]
    active.last_login = now - timedelta(days=3)
    assert sentence(active, now) == "Entró hace 3 días."
    active.last_login = now - timedelta(seconds=10)
    assert sentence(active, now) == "Entró hace un momento."
    assert "Sin rol asignado: cuenta como miembro." in sentence(world["norole"], now, no_role=True)
    inactive = world["active"]
    inactive.is_active = False
    assert sentence(inactive, now) == "Cuenta desactivada en la administración técnica."


def test_the_page_shows_the_sentence_and_the_access_chips(admin_person, world):
    TeamMember.objects.create(person=world["never"], tailscale_invited=True)
    device = TotpDevice.objects.create(
        person=world["lead"], secret="x", confirmed_at=timezone.now()
    )
    assert device
    html = body(get(admin_person))
    assert "Todavía no puede entrar" in html and "Sin acceso. Sus datos" in html
    assert "Contraseña: no" in html and "Tailscale: invitada" in html
    assert "2FA activo" in html and "Sin rol" in html and "Sin disciplina" in html
    assert "Responsable" in html and "Miembro" in html


def test_the_fixed_admin_is_marked(admin_person, settings):
    settings.BOOTSTRAP_ADMINS = [admin_person.login]
    assert "Admin fija" in body(get(admin_person))


# --- consultas acotadas ----------------------------------------------------------------------------------------


def measure(client, url=URL):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    own = own_queries(ctx.captured_queries)
    return len(ctx), len(own)


def test_the_accounts_queries_do_not_grow_with_the_people(admin_person, make_person):
    client = tailscale_client(admin_person.login)
    client.get(URL)
    for i in range(5):
        p = make_person(f"p{i}@example.com", status="pending" if i % 2 else "approved")
        TeamMember.objects.create(person=p)
    small = measure(client)
    for i in range(55):
        p = make_person(f"q{i}@example.com", status=("pending", "approved", "suspended")[i % 3])
        TeamMember.objects.create(person=p)
        TotpDevice.objects.create(person=p, secret="x", confirmed_at=timezone.now())
    large = measure(client)
    assert small == large
    assert large[1] <= 8


def test_the_list_is_paginated(admin_person, make_person):
    for i in range(60):
        make_person(f"m{i:02d}@example.com")
    client = tailscale_client(admin_person.login)
    first = body(client.get(URL))
    assert "Página 1 de 2" in first and len(logins_in(first)) == admin_center.PAGE_SIZE
    second = body(client.get(URL, {"pagina": 2}))
    assert len(logins_in(second)) == 61 - admin_center.PAGE_SIZE
    assert (
        client.get(URL, {"pagina": "zzz"}).status_code == 200
    )  # un valor raro cae en la última página


# --- aprobar y rechazar ------------------------------------------------------------------------------------------


def test_approve_sets_role_disciplines_and_logs_and_a_second_try_is_404(admin_person, world):
    call_command("seed_catalog", verbosity=0)
    slugs = list(Discipline.objects.values_list("slug", flat=True)[:2])
    target = world["pending"]
    url = f"{URL}{target.pk}/aprobar/"
    response = post(admin_person, url, {"role": "lead", "disciplines": slugs, "back": "centro"})
    assert response.status_code == 302 and response["Location"].startswith("/administracion/#p")
    target = Person.objects.get(pk=target.pk)
    assert target.status == "approved" and target.role == "lead"
    assert set(target.disciplines.values_list("slug", flat=True)) == set(slugs)
    assert ModerationLog.objects.filter(action="approve_person", object_id=target.pk).count() == 1
    assert post(admin_person, url).status_code == 404
    assert ModerationLog.objects.filter(action="approve_person", object_id=target.pk).count() == 1


def test_approve_defaults_to_member_and_ignores_an_admin_role(admin_person, world):
    target = world["pending"]
    post(admin_person, f"{URL}{target.pk}/aprobar/", {"role": "admin"})
    assert Person.objects.get(pk=target.pk).role == "member"


def test_reject_leaves_the_person_without_access_and_logs(admin_person, world):
    target = world["pending"]
    response = post(admin_person, f"{URL}{target.pk}/rechazar/", {"back": "cuentas"})
    assert response.status_code == 302 and response["Location"].startswith(URL)
    assert Person.objects.get(pk=target.pk).status == "suspended"
    assert ModerationLog.objects.filter(action="reject_person", object_id=target.pk).count() == 1
    assert post(admin_person, f"{URL}{target.pk}/rechazar/").status_code == 404


def test_the_back_field_only_accepts_the_two_known_screens(admin_person, world):
    target = world["pending"]
    response = post(admin_person, f"{URL}{target.pk}/rechazar/", {"back": "//evil.com"})
    assert response["Location"].startswith(URL) and "evil" not in response["Location"]


# --- suspender y reactivar ---------------------------------------------------------------------------------------


def test_suspend_cuts_access_and_reactivate_gives_it_back_with_a_record(admin_person, world):
    target = world["active"]
    victim = tailscale_client(target.login)
    assert victim.get("/").status_code == 200
    assert post(admin_person, f"{URL}{target.pk}/suspender/").status_code == 302
    assert Person.objects.get(pk=target.pk).status == "suspended"
    cut = victim.get("/")
    assert cut.status_code == 403 and "Centro de administración" not in cut.content.decode()
    assert ModerationLog.objects.filter(action="suspend_person", object_id=target.pk).count() == 1
    assert post(admin_person, f"{URL}{target.pk}/reactivar/").status_code == 302
    assert Person.objects.get(pk=target.pk).status == "approved"
    assert victim.get("/").status_code == 200
    assert (
        ModerationLog.objects.filter(action="reactivate_person", object_id=target.pk).count() == 1
    )


def test_suspend_and_reactivate_are_idempotent(admin_person, world):
    target = world["active"]
    for _ in range(3):
        post(admin_person, f"{URL}{target.pk}/suspender/")
    assert ModerationLog.objects.filter(action="suspend_person").count() == 1
    for _ in range(3):
        post(admin_person, f"{URL}{target.pk}/reactivar/")
    assert ModerationLog.objects.filter(action="reactivate_person").count() == 1
    other = world["never"]  # reactivar a quien no estaba suspendida no hace nada ni deja registro
    post(admin_person, f"{URL}{other.pk}/reactivar/")
    assert ModerationLog.objects.filter(action="reactivate_person").count() == 1


def test_nobody_suspends_herself_or_the_fixed_admin(admin_person, make_person, settings):
    response = post(admin_person, f"{URL}{admin_person.pk}/suspender/")
    assert response.status_code == 302
    assert Person.objects.get(pk=admin_person.pk).status == "approved"
    other_admin = make_person("otra-admin@example.com", role="admin")
    settings.BOOTSTRAP_ADMINS = [other_admin.login]
    post(admin_person, f"{URL}{other_admin.pk}/suspender/")
    assert Person.objects.get(pk=other_admin.pk).status == "approved"
    assert not ModerationLog.objects.filter(action="suspend_person").exists()
    page = body(get(admin_person))
    assert f'action="{URL}{admin_person.pk}/suspender/"' not in page
    assert f'action="{URL}{other_admin.pk}/suspender/"' not in page


def test_a_pending_person_is_rejected_not_suspended(admin_person, world):
    post(admin_person, f"{URL}{world['pending'].pk}/suspender/")
    assert Person.objects.get(pk=world["pending"].pk).status == "pending"
    assert not ModerationLog.objects.filter(action="suspend_person").exists()


def test_the_buttons_match_the_state(admin_person, world):
    page = body(get(admin_person))
    assert f"{URL}{world['suspended'].pk}/reactivar/" in page
    assert f"{URL}{world['suspended'].pk}/suspender/" not in page
    assert f"{URL}{world['active'].pk}/suspender/" in page
    assert f"{URL}{world['pending'].pk}/aprobar/" in page
    assert f"{URL}{world['pending'].pk}/enlace/" not in page  # aún no puede recibir enlace


# --- rol ---------------------------------------------------------------------------------------------------------


def test_change_role_and_the_rules(admin_person, world, settings):
    target = world["active"]
    post(admin_person, f"{URL}{target.pk}/rol/", {"role": "lead"})
    assert Person.objects.get(pk=target.pk).role == "lead"
    assert ModerationLog.objects.filter(action="update_person", object_id=target.pk).count() == 1
    post(
        admin_person, f"{URL}{target.pk}/rol/", {"role": "lead"}
    )  # sin cambios: no repite el registro
    assert ModerationLog.objects.filter(action="update_person", object_id=target.pk).count() == 1
    post(admin_person, f"{URL}{target.pk}/rol/", {"role": "dios"})
    assert Person.objects.get(pk=target.pk).role == "lead"
    post(admin_person, f"{URL}{admin_person.pk}/rol/", {"role": "member"})  # no el propio
    assert Person.objects.get(pk=admin_person.pk).role == "admin"
    settings.BOOTSTRAP_ADMINS = [target.login]  # la fija no cambia de rol
    post(admin_person, f"{URL}{target.pk}/rol/", {"role": "member"})
    assert Person.objects.get(pk=target.pk).role == "lead"


def test_a_person_without_role_gets_one_assigned(admin_person, world):
    target = world["norole"]
    assert not target.groups.exists()
    post(admin_person, f"{URL}{target.pk}/rol/", {"role": "member"})
    assert target.groups.filter(name="member").exists()
    assert "Sin rol <b>0</b>" in body(get(admin_person))


# --- enlaces: se muestran una sola vez ------------------------------------------------------------------------


def token_of(text):
    return re.search(r"/(?:registro|inscripcion)/([^/\"<\s]+)/", text).group(1)


def test_the_personal_link_is_shown_once_and_stored_nowhere(admin_person, world):
    client = tailscale_client(admin_person.login)
    target = world["never"]
    response = client.post(f"{URL}{target.pk}/enlace/", {"back": "cuentas"})
    assert response.status_code == 302
    first = client.get(URL).content.decode()
    token = token_of(first)
    assert f"/registro/{token}/" in first and "Enlace de registro de nunca" in first
    assert token_of(client.get(URL).content.decode() + "/registro/ninguno/") == "ninguno"
    assert f"/registro/{token}/" not in client.get(URL).content.decode()
    # la bitácora y las tablas de personas no guardan el enlace
    log = list(ModerationLog.objects.values_list("summary", "reason"))
    assert all(token not in text for pair in log for text in pair)
    assert not any(token in str(v) for v in Person.objects.values_list("invite_nonce", "password"))
    assert services.resolve_signup_token(token) == Person.objects.get(pk=target.pk)


def test_a_pending_or_suspended_person_gets_no_personal_link(admin_person, world):
    for key in ("pending", "suspended"):
        post(admin_person, f"{URL}{world[key].pk}/enlace/")
    assert not ModerationLog.objects.filter(action="signup_link").exists()


def test_the_team_link_is_shown_once_and_the_old_one_dies(admin_person):
    client = tailscale_client(admin_person.login)
    response = client.post("/administracion/enlace-equipo/", {"days": "7"})
    assert response.status_code == 302 and response["Location"].endswith("#enlace")
    first = client.get("/administracion/").content.decode()
    token = token_of(first)
    assert f"/inscripcion/{token}/" in first
    assert "/inscripcion/" not in client.get("/administracion/").content.decode()
    old = team_link.resolve(token)
    assert old is not None
    client.post("/administracion/enlace-equipo/", {"days": "30"})
    assert team_link.resolve(token) is None  # generar uno nuevo revoca el anterior
    assert not any(token in s for s in ModerationLog.objects.values_list("summary", flat=True))
    assert TeamSignupLink.objects.count() == 2 and all(
        token not in h for h in TeamSignupLink.objects.values_list("secret_hash", flat=True)
    )


def test_team_link_validity_and_revocation(admin_person):
    client = tailscale_client(admin_person.login)
    client.post("/administracion/enlace-equipo/", {"days": "99"})
    assert team_link.active_link() is None
    client.post("/administracion/enlace-equipo/", {"days": "14"})
    assert team_link.active_link() is not None
    client.post("/administracion/enlace-equipo/revocar/")
    assert team_link.active_link() is None
    client.post("/administracion/enlace-equipo/revocar/")  # repetir no falla
    assert ModerationLog.objects.filter(action="team_link_revoke").count() == 1
    assert client.get("/administracion/enlace-equipo/").status_code == 405


# --- escape --------------------------------------------------------------------------------------------------------


def test_names_are_escaped_everywhere(admin_person, world):
    evil = world["active"]
    evil.display_name = "<script>alert(1)</script>"
    evil.save(update_fields=["display_name"])
    for estado in ("", "activa"):
        html = body(get(admin_person, estado=estado))
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    client = tailscale_client(admin_person.login)
    client.post(f"{URL}{evil.pk}/suspender/")
    page = client.get(URL).content.decode()  # el mensaje de la acción lleva el nombre
    assert "quedó suspendida" in page and "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; quedó suspendida" in page
