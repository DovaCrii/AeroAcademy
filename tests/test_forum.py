from datetime import timedelta

import pytest
from django.core.management import call_command

from apps.catalog.models import Discipline
from apps.catalog.seeding import SeedError
from apps.community import forum
from apps.community.models import Category, Post, Thread
from apps.community.seeding import load_forum, validate_forum
from apps.gamification import game
from apps.gamification.models import XPEvent

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def cat(slug="general"):
    return Category.objects.get(slug=slug)


def question(author, title="¿Cómo hago un corte?", **kw):
    return forum.create_thread(author, cat(), "question", title, "Detalle", **kw)


def accepted_xp(person):
    return sum(
        XPEvent.objects.filter(person=person, kind="accepted_answer").values_list(
            "points", flat=True
        )
    )


# --- semillas -------------------------------------------------------------------------------------------------


def test_forum_seed_loads_and_retires():
    assert Category.objects.filter(retired=False).count() == 6
    load_forum({"categories": [{"slug": "solo", "name": "Solo"}]})
    assert Category.objects.get(slug="general").retired is True
    call_command("seed_catalog", verbosity=0)
    assert Category.objects.get(slug="general").retired is False


def test_forum_seed_validation():
    assert validate_forum(
        {"categories": [{"slug": "a", "name": "A"}, {"slug": "a", "name": "B"}, {"slug": "b"}]}
    )
    with pytest.raises(SeedError):
        load_forum({"categories": [{"slug": "a"}]})


# --- hilos y respuestas -----------------------------------------------------------------------------------------


def test_create_thread_validates(member):
    with pytest.raises(ValueError):
        forum.create_thread(member, cat(), "question", " ", "x")
    with pytest.raises(ValueError):
        forum.create_thread(member, cat(), "question", "t", "")
    with pytest.raises(ValueError):
        forum.create_thread(member, cat(), "question", "t" * 151, "x")
    with pytest.raises(ValueError):
        forum.create_thread(member, cat(), "otra", "t", "x")
    retired = cat()
    retired.retired = True
    with pytest.raises(ValueError):
        forum.create_thread(member, retired, "question", "t", "x")


def test_reply_updates_activity_and_closed_threads_refuse(member, lead):
    t = question(member)
    old = t.last_activity_at - timedelta(days=3)
    Thread.objects.filter(pk=t.pk).update(last_activity_at=old)
    before = old
    forum.reply(t, lead, "Así")
    t.refresh_from_db()
    assert t.last_activity_at > before
    forum.set_closed(t, member, True)
    with pytest.raises(ValueError, match="cerrado"):
        forum.reply(t, lead, "Más")


# --- respuesta aceptada ----------------------------------------------------------------------------------------


def test_only_the_asker_or_a_lead_accepts(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = question(member)
    post = forum.reply(t, other, "Prueba esto")
    with pytest.raises(PermissionError):
        forum.accept(t, post, other)
    forum.accept(t, post, member)
    t.refresh_from_db()
    assert t.accepted_post == post
    forum.unaccept(t, lead)  # un responsable también puede
    t.refresh_from_db()
    assert t.accepted_post is None


def test_accepting_gives_xp_to_the_answerer_once(member, make_person):
    other = make_person("otra@lev.cl")
    t = question(member)
    post = forum.reply(t, other, "Prueba esto")
    forum.accept(t, post, member)
    forum.accept(t, post, member)
    assert accepted_xp(other) == 50


def test_changing_the_accepted_answer_moves_the_xp(member, make_person):
    a, b = make_person("a@lev.cl"), make_person("b@lev.cl")
    t = question(member)
    pa, pb = forum.reply(t, a, "A"), forum.reply(t, b, "B")
    forum.accept(t, pa, member)
    forum.accept(t, pb, member)
    assert accepted_xp(a) == 0 and accepted_xp(b) == 50


def test_unaccepting_or_deleting_the_accepted_post_revokes_xp(member, make_person):
    other = make_person("otra@lev.cl")
    t = question(member)
    post = forum.reply(t, other, "Prueba")
    forum.accept(t, post, member)
    forum.unaccept(t, member)
    assert accepted_xp(other) == 0
    forum.accept(t, post, member)
    forum.delete_post(post, other)
    t.refresh_from_db()
    assert accepted_xp(other) == 0 and t.accepted_post is None


def test_self_answers_give_no_xp(member):
    t = question(member)
    post = forum.reply(t, member, "Ya lo resolví")
    forum.accept(t, post, member)
    assert accepted_xp(member) == 0


def test_discussions_have_no_accepted_answer(member):
    t = forum.create_thread(member, cat(), "discussion", "Charla", "x")
    post = forum.reply(t, member, "y")
    with pytest.raises(ValueError):
        forum.accept(t, post, member)


def test_cannot_accept_a_post_from_another_thread_or_a_deleted_one(member, lead):
    t1, t2 = question(member), question(member, "otra")
    p2 = forum.reply(t2, lead, "x")
    with pytest.raises(ValueError):
        forum.accept(t1, p2, member)
    p1 = forum.reply(t1, lead, "y")
    forum.delete_post(p1, lead)
    with pytest.raises(ValueError):
        forum.accept(t1, p1, member)


def test_mentor_and_sabio_badges_follow_accepted_answers(member, make_person):
    expert = make_person("experta@lev.cl")
    for i in range(5):
        t = question(member, f"q{i}")
        forum.accept(t, forum.reply(t, expert, "r"), member)
    assert "mentor" in game.unlocked_badges(expert)
    assert "sabio-del-foro" not in game.unlocked_badges(expert)


def test_only_the_author_deletes_a_post(member, lead):
    t = question(member)
    post = forum.reply(t, member, "mío")
    with pytest.raises(PermissionError):
        forum.delete_post(post, lead)
    forum.delete_post(post, member)
    assert Post.objects.get(pk=post.pk).is_deleted


def test_closing_needs_the_author_or_a_lead(member, make_person):
    other = make_person("otra@lev.cl")
    t = question(member)
    with pytest.raises(PermissionError):
        forum.set_closed(t, other, True)


# --- listado ------------------------------------------------------------------------------------------------------


def test_listing_filters(member, lead):
    d = Discipline.objects.first()
    open_q = question(member, "Abierta", disciplines=[d])
    done = question(member, "Resuelta")
    forum.accept(done, forum.reply(done, lead, "r"), member)
    chat = forum.create_thread(member, cat("bentley"), "discussion", "Charla", "x")
    titles = lambda **kw: {t.title for t in forum.listing(**kw)}  # noqa: E731
    assert titles(state="open") == {"Abierta"}
    assert titles(state="answered") == {"Resuelta"}
    assert titles(kind="discussion") == {"Charla"}
    assert titles(category=cat("bentley")) == {chat.title}
    assert titles(discipline=d) == {"Abierta"}
    assert titles(q="resuel") == {"Resuelta"}
    assert forum.open_questions_count() == 1 and open_q


def test_listing_counts_only_visible_posts(member, lead):
    t = question(member)
    keep, gone = forum.reply(t, lead, "a"), forum.reply(t, lead, "b")
    forum.delete_post(gone, lead)
    assert forum.listing().get(pk=t.pk).n_posts == 1 and keep


# --- vistas -------------------------------------------------------------------------------------------------------


def test_pages_render_and_post(client_for, member, lead):
    client = client_for(member.login)
    assert client.get("/foro/").status_code == 200
    assert client.get("/foro/nuevo/").status_code == 200
    response = client.post(
        "/foro/nuevo/",
        {
            "kind": "question",
            "category": "general",
            "title": "Duda",
            "body": "Texto",
            "disciplines": [],
        },
    )
    t = Thread.objects.get()
    assert response["Location"] == f"/foro/{t.pk}/"
    client_for(lead.login).post(f"/foro/{t.pk}/", {"body": "Respuesta"})
    html = client.get(f"/foro/{t.pk}/").content.decode()
    assert "Respuesta" in html and "Aceptar esta respuesta" in html
    post = Post.objects.get()
    client.post(f"/foro/{t.pk}/aceptar/{post.pk}/")
    t.refresh_from_db()
    assert t.accepted_post == post
    assert "Respuesta aceptada" in client.get(f"/foro/{t.pk}/").content.decode()


def test_non_authors_do_not_see_accept_buttons_and_cannot_post_them(
    client_for, member, lead, make_person
):
    other = make_person("otra@lev.cl")
    t = question(member)
    post = forum.reply(t, lead, "r")
    assert (
        "Aceptar esta respuesta"
        not in client_for(other.login).get(f"/foro/{t.pk}/").content.decode()
    )
    client_for(other.login).post(f"/foro/{t.pk}/aceptar/{post.pk}/")
    t.refresh_from_db()
    assert t.accepted_post is None


def test_text_is_escaped(client_for, member):
    t = forum.create_thread(member, cat(), "question", "<b>x</b>", "<script>alert(1)</script>")
    forum.reply(t, member, "<img src=x onerror=alert(1)>")
    html = client_for(member.login).get(f"/foro/{t.pk}/").content.decode()
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "<b>x</b>" not in client_for(member.login).get("/foro/").content.decode()


def test_invalid_thread_shows_error_and_keeps_input(client_for, member):
    response = client_for(member.login).post(
        "/foro/nuevo/", {"kind": "question", "category": "", "title": "Mi título", "body": "b"}
    )
    html = response.content.decode()
    assert response.status_code == 200 and "Elige una categoría" in html and "Mi título" in html
    assert not Thread.objects.exists()


def test_pagination(client_for, member):
    for i in range(45):
        question(member, f"Hilo {i}")
    client = client_for(member.login)
    first = client.get("/foro/").content.decode()
    assert "Página 1 de 3" in first and first.count('<li class="thread') == 20
    third = client.get("/foro/?pagina=3").content.decode()
    assert third.count('<li class="thread') == 5
    assert "pagina=2" in client.get("/foro/?q=Hilo").content.decode()


def test_forum_requires_approval(client_for, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(pending.login).get("/foro/").status_code != 200


def test_list_query_count_is_flat(client_for, member, django_assert_max_num_queries):
    for i in range(15):
        question(member, f"Hilo {i}")
    with django_assert_max_num_queries(30):
        assert client_for(member.login).get("/foro/").status_code == 200


def test_home_counter_and_nav(client_for, member):
    question(member)
    html = client_for(member.login).get("/").content.decode()
    assert "1</b> consultas sin respuesta" in html and 'href="/foro/"' in html
