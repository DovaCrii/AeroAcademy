import pytest
from django.core.management import call_command

from apps.community import services
from apps.community.models import Note
from apps.gamification import game
from apps.gamification.models import XPEvent
from apps.paths.models import LearningPath, Level

pytestmark = pytest.mark.django_db
FORMA, BENTLEY = "forma-revit", "bentley-learn"


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def forma():
    return LearningPath.objects.get(slug=FORMA)


def note(author, text="Funcionó con la plantilla.", type="works", **kw):
    return services.create_note(author, forma(), text, type, **kw)


def points(person):
    return sum(XPEvent.objects.filter(person=person, kind="note").values_list("points", flat=True))


# --- crear ----------------------------------------------------------------------------------------------------------


def test_create_and_list(member):
    n = note(member)
    assert list(services.notes_for(forma())) == [n]


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
def test_text_is_validated(member, text):
    with pytest.raises(ValueError):
        note(member, text)


def test_unknown_type_and_foreign_level_are_rejected(member):
    with pytest.raises(ValueError):
        note(member, type="reply")
    other_level = Level.objects.filter(path__slug=BENTLEY).first()
    with pytest.raises(ValueError, match="no es de esta ruta"):
        note(member, level=other_level)


def test_replies_inherit_context_and_cannot_nest(member, lead):
    level = Level.objects.filter(path=forma()).first()
    parent = note(member, level=level)
    reply = services.create_note(lead, forma(), "Gracias", "reply", parent=parent)
    assert reply.type == "reply" and reply.level == level and reply.parent == parent
    with pytest.raises(ValueError):
        services.create_note(member, forma(), "x", "reply", parent=reply)
    parent.is_deleted = True
    with pytest.raises(ValueError):
        services.create_note(member, forma(), "x", "reply", parent=parent)


def test_a_reply_must_match_the_notes_path(member):
    parent = note(member)
    other = LearningPath.objects.get(slug=BENTLEY)
    with pytest.raises(ValueError):
        services.create_note(member, other, "x", "reply", parent=parent)


# --- XP ---------------------------------------------------------------------------------------------------------------


def test_works_and_tip_give_xp_but_fails_and_ask_do_not(member):
    note(member, type="works")
    note(member, type="tip")
    note(member, type="fails")
    note(member, type="ask")
    assert points(member) == 10
    assert (
        XPEvent.objects.filter(person=member, kind="note").count() == 4
    )  # todas cuentan para la insignia


def test_daily_xp_cap(member):
    for _ in range(7):
        note(member)
    assert points(member) == 25  # 5 notas × 5 XP


def test_first_note_earns_primera_nube_even_without_xp(member):
    note(member, type="ask")
    assert "primera-nube" in game.unlocked_badges(member)


def test_deleting_revokes_xp_and_badge(member):
    n = note(member)
    services.delete_note(n, member)
    assert points(member) == 0 and "primera-nube" not in game.unlocked_badges(member)


# --- borrar -----------------------------------------------------------------------------------------------------------


def test_only_the_author_deletes(client_for, member, lead):
    n = note(member)
    with pytest.raises(PermissionError):
        services.delete_note(n, lead)
    response = client_for(lead.login).post(f"/notas/{n.pk}/eliminar/")
    n.refresh_from_db()
    assert response.status_code == 302 and n.is_deleted is False
    client_for(member.login).post(f"/notas/{n.pk}/eliminar/")
    n.refresh_from_db()
    assert n.is_deleted is True


def test_deleting_a_note_hides_its_replies(member, lead):
    parent = note(member)
    services.create_note(lead, forma(), "respuesta", "reply", parent=parent)
    services.delete_note(parent, member)
    assert list(services.notes_for(forma())) == []
    assert Note.objects.filter(parent=parent).count() == 1  # se conserva, solo se oculta


# --- vistas ------------------------------------------------------------------------------------------------------------


def test_notes_page_posts_and_filters(client_for, member):
    client = client_for(member.login)
    level = Level.objects.filter(path=forma()).first()
    client.post(
        f"/rutas/{FORMA}/notas/", {"type": "tip", "level": level.code, "text": "Usa la vista 3D"}
    )
    client.post(f"/rutas/{FORMA}/notas/", {"type": "fails", "text": "No abre el vínculo"})
    html = client.get(f"/rutas/{FORMA}/notas/").content.decode()
    assert "Usa la vista 3D" in html and "No abre el vínculo" in html
    only_tips = client.get(f"/rutas/{FORMA}/notas/?tipo=tip").content.decode()
    assert "Usa la vista 3D" in only_tips and "No abre el vínculo" not in only_tips
    by_level = client.get(f"/rutas/{FORMA}/notas/?nivel={level.code}").content.decode()
    assert "Usa la vista 3D" in by_level and "No abre el vínculo" not in by_level


def test_text_is_escaped(client_for, member):
    client = client_for(member.login)
    client.post(f"/rutas/{FORMA}/notas/", {"type": "tip", "text": "<script>alert(1)</script>"})
    html = client.get(f"/rutas/{FORMA}/notas/").content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_invalid_post_shows_an_error_and_saves_nothing(client_for, member):
    response = client_for(member.login).post(
        f"/rutas/{FORMA}/notas/", {"type": "tip", "text": " "}, follow=True
    )
    assert "Escribe la nota" in response.content.decode() and not Note.objects.exists()


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com", "javascript:x"])
def test_next_is_never_an_open_redirect(client_for, member, target):
    response = client_for(member.login).post(
        f"/rutas/{FORMA}/notas/", {"type": "tip", "text": "ok", "next": target}
    )
    assert response["Location"] == f"/rutas/{FORMA}/notas/"


def test_reply_via_http(client_for, member, lead):
    parent = note(member)
    client_for(lead.login).post(f"/notas/{parent.pk}/responder/", {"text": "Gracias"})
    assert Note.objects.filter(parent=parent, author=lead).exists()
    assert "Gracias" in client_for(member.login).get(f"/rutas/{FORMA}/notas/").content.decode()


def test_unpublished_paths_are_hidden_from_members(client_for, member):
    LearningPath.objects.filter(slug=FORMA).update(is_published=False)
    assert client_for(member.login).get(f"/rutas/{FORMA}/notas/").status_code == 404
    n = Note.objects.create(author=member, path=forma(), type="tip", text="x")
    assert client_for(member.login).post(f"/notas/{n.pk}/eliminar/").status_code == 404


def test_pending_people_cannot_write(client_for, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    response = client_for(pending.login).post(
        f"/rutas/{FORMA}/notas/", {"type": "tip", "text": "x"}
    )
    assert response.status_code != 200 and not Note.objects.exists()


def test_world_panels_show_the_latest_notes(client_for, member):
    note(member, "Mira esta nota del capítulo")
    for slug in (FORMA, BENTLEY):
        html = client_for(member.login).get(f"/rutas/{slug}/").content.decode()
        assert "Notas del equipo" in html and f"/rutas/{slug}/notas/" in html
    html = client_for(member.login).get(f"/rutas/{FORMA}/").content.decode()
    assert "Mira esta nota" in html


def test_notes_page_query_count_is_flat(client_for, member, lead, django_assert_max_num_queries):
    for i in range(10):
        n = note(member, f"nota {i}")
        services.create_note(lead, forma(), "re", "reply", parent=n)
    with django_assert_max_num_queries(30):
        assert client_for(member.login).get(f"/rutas/{FORMA}/notas/").status_code == 200
