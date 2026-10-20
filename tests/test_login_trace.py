"""Centro de administración (D42), P1-3: por dónde entra cada cuenta (`LoginTrace`), sin IP ni navegador."""

from datetime import timedelta

import pytest
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import signals
from apps.accounts.models import LoginTrace, Person
from apps.core import admin_center
from tests.conftest import own_queries, tailscale_client

pytestmark = pytest.mark.django_db
GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    cache.clear()
    monkeypatch.setattr(admin_center, "public_door_up", lambda: False)
    yield
    cache.clear()


def with_password(person, raw=GOOD):
    person.set_password(raw)
    person.save(update_fields=["password"])
    return person


def password_login(person, **extra):
    extra.setdefault("REMOTE_ADDR", "127.0.0.1")
    client = Client(**extra)
    response = client.post("/entrar/", {"email": person.login, "password": GOOD})
    assert response.status_code == 302
    return client


def trace(person):
    return LoginTrace.objects.get(person=person)


def test_the_tailscale_header_marks_only_the_tailscale_way(member):
    assert tailscale_client(member.login).get("/").status_code == 200
    row = trace(member)
    assert row.last_tailscale_at is not None
    assert row.last_password_at is None and row.last_public_at is None
    assert row.via_text() == "por Tailscale"


def test_the_password_form_marks_only_the_password_way(member):
    password_login(with_password(member))
    row = trace(member)
    assert row.last_password_at is not None
    assert row.last_tailscale_at is None and row.last_public_at is None
    assert row.via_text() == "con contraseña"


def test_the_public_door_marks_only_the_public_way(member, settings):
    settings.PUBLIC_DOOR = True
    password_login(with_password(member))
    row = trace(member)
    assert row.last_public_at is not None
    assert row.last_tailscale_at is None and row.last_password_at is None
    assert row.via_text() == "desde internet (puerta pública)"


def test_each_way_keeps_its_own_date_and_the_latest_one_speaks(member):
    tailscale_client(member.login).get("/")
    old = timezone.now() - timedelta(days=2)
    LoginTrace.objects.filter(person=member).update(last_tailscale_at=old)
    password_login(with_password(member))
    row = trace(member)
    assert row.last_tailscale_at == old and row.last_password_at > old
    assert row.via_text() == "con contraseña"
    assert LoginTrace.objects.filter(person=member).count() == 1  # una sola fila por persona
    password_login(member)
    assert LoginTrace.objects.filter(person=member).count() == 1


def test_a_failure_to_record_never_stops_anyone_from_entering(member, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("base bloqueada")

    monkeypatch.setattr(LoginTrace.objects, "filter", boom)
    monkeypatch.setattr(LoginTrace.objects, "create", boom)
    assert tailscale_client(member.login).get("/").status_code == 200
    client = password_login(with_password(member))
    assert client.get("/").status_code == 200
    assert not LoginTrace.objects.exists()


def test_a_login_without_a_request_is_ignored(member):
    user_logged_in.send(sender=Person, request=None, user=member)
    assert not LoginTrace.objects.exists()
    assert signals.trace_field(object()) == "last_password_at"


def test_nothing_that_identifies_the_machine_is_stored(member):
    assert {f.name for f in LoginTrace._meta.get_fields()} == {
        "id",
        "person",
        "last_tailscale_at",
        "last_password_at",
        "last_public_at",
    }
    password_login(
        with_password(member),
        REMOTE_ADDR="127.0.0.1",
        HTTP_USER_AGENT="Agente-Centinela/9.9",
        HTTP_X_FORWARDED_FOR="203.0.113.77",
    )
    tailscale_client(member.login).get("/", HTTP_USER_AGENT="Agente-Centinela/9.9")
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM accounts_logintrace")
        stored = " ".join(str(v) for row in cur.fetchall() for v in row)
    assert "Agente" not in stored and "203.0.113" not in stored and "127.0.0.1" not in stored


def test_the_trace_goes_with_the_person(member):
    tailscale_client(member.login).get("/")
    member.delete()
    assert not LoginTrace.objects.exists()


# --- se ve en las cuentas --------------------------------------------------------------------------------------


def test_the_accounts_page_says_how_each_one_enters(admin_person, member, make_person):
    other = make_person("otra@example.com")
    tailscale_client(member.login).get("/")
    Person.objects.filter(pk=member.pk).update(last_login=timezone.now() - timedelta(days=3))
    password_login(with_password(other))
    Person.objects.filter(pk=other.pk).update(last_login=timezone.now() - timedelta(hours=5))
    html = tailscale_client(admin_person.login).get("/administracion/cuentas/").content.decode()
    assert "Entró hace 3 días por Tailscale." in html
    assert "Entró hace 5 horas con contraseña." in html
    assert "Entra por Tailscale (" in html and "Entra con contraseña (" in html


def test_without_a_trace_the_sentence_only_says_when(admin_person, make_person):
    old = make_person("antigua@example.com")
    Person.objects.filter(pk=old.pk).update(last_login=timezone.now() - timedelta(days=9))
    html = tailscale_client(admin_person.login).get("/administracion/cuentas/").content.decode()
    assert "Entró hace 1 semana." in html


def test_the_accounts_page_stays_within_its_query_budget_with_traces(admin_person, make_person):
    client = tailscale_client(admin_person.login)
    client.get("/administracion/cuentas/")

    def own():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/administracion/cuentas/").status_code == 200
        return len(own_queries(ctx.captured_queries))

    for i in range(5):
        p = make_person(f"a{i}@example.com")
        LoginTrace.objects.create(person=p, last_tailscale_at=timezone.now())
    small = own()
    for i in range(55):
        p = make_person(f"b{i}@example.com")
        LoginTrace.objects.create(
            person=p, last_password_at=timezone.now(), last_public_at=timezone.now()
        )
    assert own() == small <= 8
