"""Centro de administración (D42), P1-4: bitácora de solo lectura."""

import re
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.community import moderation
from apps.community.models import ModerationLog
from apps.core import admin_center
from tests.conftest import own_queries, tailscale_client

pytestmark = pytest.mark.django_db
URL = "/administracion/bitacora/"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    cache.clear()
    monkeypatch.setattr(admin_center, "public_door_up", lambda: False)
    yield
    cache.clear()


def fill(actor, n, action="approve_person", summary="Ana"):
    base = timezone.now() - timedelta(days=1)
    for i in range(n):
        entry = moderation.log(actor, action, actor, f"{summary} {i}")
        ModerationLog.objects.filter(pk=entry.pk).update(created_at=base + timedelta(seconds=i))


def body(response):
    return response.content.decode().split("<main")[1]


def test_lead_and_admin_read_it_member_and_others_get_404(admin_person, lead, member, settings):
    assert tailscale_client(admin_person.login).get(URL).status_code == 200
    assert tailscale_client(lead.login).get(URL).status_code == 200
    assert tailscale_client(member.login).get(URL).status_code == 404
    anon = Client(REMOTE_ADDR="127.0.0.1")
    assert anon.get(URL).status_code == 302
    settings.PUBLIC_DOOR = True
    assert Client(REMOTE_ADDR="127.0.0.1").get(URL).status_code == 404


def test_the_public_door_hides_it_even_from_an_admin(admin_person, settings):
    admin_person.set_password("Clave-de-prueba-9271!")
    admin_person.save(update_fields=["password"])
    client = Client(REMOTE_ADDR="127.0.0.1")
    client.post("/entrar/", {"email": admin_person.login, "password": "Clave-de-prueba-9271!"})
    assert client.get(URL).status_code == 200
    settings.PUBLIC_DOOR = True
    settings.PUBLIC_REQUIRE_SECOND_FACTOR = False
    assert client.get(URL).status_code == 404


def test_it_is_read_only(admin_person, lead, member):
    fill(admin_person, 2)
    html = body(tailscale_client(admin_person.login).get(URL)).split("</main>")[0]
    assert "<form" in html  # solo el filtro
    assert 'method="post"' not in html and "csrfmiddlewaretoken" not in html
    for who, status in ((admin_person, 405), (lead, 405), (member, 404)):
        assert tailscale_client(who.login).post(URL).status_code == status


def test_newest_first_with_who_what_and_when(admin_person, lead):
    entry = moderation.log(lead, "suspend_person", lead, "Marta", "motivo claro")
    fill(admin_person, 3)
    html = body(tailscale_client(admin_person.login).get(URL))
    assert html.index("Marta") < html.index("Ana 2") < html.index("Ana 0")
    assert "luis" in html and "Persona suspendida" in html and "Motivo: motivo claro" in html
    assert f"{timezone.localtime(entry.created_at):%d/%m/%Y %H:%M}" in html


def test_paginated_by_50(admin_person):
    fill(admin_person, 120)
    client = tailscale_client(admin_person.login)
    first = body(client.get(URL))
    assert len(re.findall(r"<time ", first)) == 50 and "Página 1 de 3" in first
    last = body(client.get(URL, {"pagina": 3}))
    assert len(re.findall(r"<time ", last)) == 20
    assert client.get(URL, {"pagina": "x"}).status_code == 200


def test_filter_by_action_uses_a_whitelist(admin_person):
    fill(admin_person, 3, "suspend_person", "Suspendida")
    fill(admin_person, 2, "approve_person", "Aprobada")
    client = tailscale_client(admin_person.login)
    only = body(client.get(URL, {"accion": "suspend_person"}))
    assert only.count("<time ") == 3 and "Aprobada" not in only
    assert '<option value="suspend_person" selected>' in only
    everything = body(client.get(URL, {"accion": "'; DROP TABLE x;--"}))
    assert everything.count("<time ") == 5  # una acción desconocida se ignora
    assert "Ninguna acción de ese tipo" in body(client.get(URL, {"accion": "pin"}))


def test_unknown_actions_still_show_escaped_and_a_removed_actor_is_named(admin_person, lead):
    moderation.log(lead, "accion_nueva<b>", lead, "algo")
    lead.delete()
    html = body(tailscale_client(admin_person.login).get(URL))
    assert "accion_nueva&lt;b&gt;" in html and "accion_nueva<b>" not in html
    assert "Alguien que ya no está" in html


def test_text_is_escaped(admin_person):
    moderation.log(
        admin_person,
        "hide",
        admin_person,
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(2)>",
    )
    admin_person.display_name = "<script>alert(3)</script>"
    admin_person.save(update_fields=["display_name"])
    html = body(tailscale_client(admin_person.login).get(URL))
    for raw in ("<script>alert", "<img src=x"):
        assert raw not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "&lt;img src=x" in html


def test_queries_do_not_grow_with_the_entries(admin_person):
    client = tailscale_client(admin_person.login)
    client.get(URL)

    def own():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(URL).status_code == 200
        return len(own_queries(ctx.captured_queries))

    fill(admin_person, 3)
    small = own()
    fill(admin_person, 120)
    assert own() == small <= 6
    with CaptureQueriesContext(connection) as ctx:
        client.get(URL, {"pagina": 2, "accion": "approve_person"})
    assert len(own_queries(ctx.captured_queries)) <= 6


def test_the_center_links_to_the_log_for_lead_and_admin(admin_person, lead):
    for person in (admin_person, lead):
        html = body(tailscale_client(person.login).get("/administracion/"))
        assert 'href="/administracion/bitacora/"' in html
