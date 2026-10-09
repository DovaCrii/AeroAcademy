import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.community import forum, moderation, opinions
from apps.community.models import Category, PollVote, Reaction
from apps.gamification import game
from apps.gamification.models import XPEvent

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def cat(slug="general"):
    return Category.objects.get(slug=slug)


def thread(author, slug="general", title="Idea", **kw):
    return forum.create_thread(author, cat(slug), "discussion", title, "Detalle", **kw)


def idea(author, options="Sí\nNo\nQuizá"):
    return thread(author, "ideas-mejoras", poll_options=options)


def reaction_xp(person):
    return sum(
        XPEvent.objects.filter(person=person, kind="reaction").values_list("points", flat=True)
    )


# --- reacciones -----------------------------------------------------------------------------------------------------


def test_reaction_toggles_once_per_kind(member, lead):
    t = thread(member)
    assert opinions.toggle_reaction(lead, t, "idea") is True
    assert opinions.toggle_reaction(lead, t, "tested") is True
    assert Reaction.objects.filter(thread=t).count() == 2
    assert opinions.toggle_reaction(lead, t, "idea") is False
    assert Reaction.objects.filter(thread=t).count() == 1


def test_reaction_rules(member, lead):
    t = thread(member)
    post = forum.reply(t, lead, "Respuesta")
    with pytest.raises(ValueError):
        opinions.toggle_reaction(lead, t, "nope")
    with pytest.raises(ValueError):
        opinions.toggle_reaction(member, t, "useful")  # no a lo propio
    moderation.set_hidden(post, lead, True, "spam")
    with pytest.raises(ValueError):
        opinions.toggle_reaction(member, post, "useful")  # no a lo oculto
    moderation.set_hidden(t, lead, True, "spam")
    with pytest.raises(ValueError):
        opinions.toggle_reaction(lead, t, "useful")


def test_useful_xp_idempotent_revoked_and_capped(member, make_person, lead):
    t = thread(member)
    opinions.toggle_reaction(lead, t, "useful")
    assert reaction_xp(member) == 1
    opinions.resync_xp(t)
    opinions.resync_xp(t)
    assert reaction_xp(member) == 1  # no duplica
    opinions.toggle_reaction(lead, t, "idea")  # otras reacciones no dan XP
    assert reaction_xp(member) == 1
    opinions.toggle_reaction(lead, t, "useful")  # quitar la revoca
    assert reaction_xp(member) == 0
    opinions.toggle_reaction(lead, t, "useful")
    moderation.set_hidden(t, lead, True, "fuera de tema")  # ocultar la revoca
    assert reaction_xp(member) == 0
    moderation.set_hidden(t, lead, False)  # mostrar la devuelve
    assert reaction_xp(member) == 1
    # tope diario
    for i in range(opinions.DAILY_REACTION_XP + 3):
        fan = make_person(f"fan{i}@lev.cl")
        opinions.toggle_reaction(fan, thread(member, title=f"H{i}"), "useful")
    assert reaction_xp(member) == opinions.DAILY_REACTION_XP


def test_deleting_post_revokes_xp(member, lead):
    t = thread(lead)
    post = forum.reply(t, member, "Mi aporte")
    opinions.toggle_reaction(lead, post, "useful")
    assert reaction_xp(member) == 1
    forum.delete_post(post, member)
    assert reaction_xp(member) == 0
    assert game.total_xp(member) >= 0


def test_clear_reactions_only_when_hidden(member, lead, make_person):
    t = thread(member)
    opinions.toggle_reaction(lead, t, "idea")
    with pytest.raises(ValueError):
        opinions.clear_reactions(t, lead)
    moderation.set_hidden(t, lead, True, "x")
    with pytest.raises(PermissionError):
        opinions.clear_reactions(t, make_person("otra@lev.cl"))
    assert opinions.clear_reactions(t, lead) == 1
    assert not Reaction.objects.filter(thread=t).exists()


# --- encuestas ------------------------------------------------------------------------------------------------------


def test_poll_options_validation(member):
    with pytest.raises(ValueError):
        idea(member, "solo una")
    with pytest.raises(ValueError):
        idea(member, "\n".join(f"o{i}" for i in range(7)))
    with pytest.raises(ValueError):
        thread(member, "general", poll_options="a\nb")  # solo Ideas y mejoras
    assert idea(member, "A\na\nB").poll_options.count() == 2  # sin repetidas


def test_vote_change_and_close(member, lead):
    t = idea(member)
    first, second = t.poll_options.all()[:2]
    opinions.vote(t, lead, first.pk)
    opinions.vote(t, lead, second.pk)  # cambia, no suma
    assert PollVote.objects.filter(thread=t).count() == 1
    assert opinions.poll_context(t, lead)["mine"] == second.pk
    forum.set_closed(t, member, True)
    with pytest.raises(ValueError):
        opinions.vote(t, lead, first.pk)
    ctx = opinions.poll_context(t, lead)
    assert ctx["open"] is False and ctx["total"] == 1
    assert [o["pct"] for o in ctx["options"]] == [0, 100, 0]


def test_vote_rejects_foreign_option(member, lead):
    t, other = idea(member), idea(member)
    with pytest.raises(ValueError):
        opinions.vote(t, lead, other.poll_options.first().pk)
    with pytest.raises(ValueError):
        opinions.vote(t, lead, "abc")


def test_add_poll_later_by_author_only(member, make_person):
    t = thread(member, "ideas-mejoras")
    with pytest.raises(PermissionError):
        opinions.add_poll(t, make_person("x@lev.cl"), "a\nb")
    opinions.add_poll(t, member, "a\nb")
    with pytest.raises(ValueError):
        opinions.add_poll(t, member, "c\nd")


def test_clear_votes_requires_hidden(member, lead):
    t = idea(member)
    opinions.vote(t, lead, t.poll_options.first().pk)
    with pytest.raises(ValueError):
        opinions.clear_votes(t, lead)
    moderation.set_hidden(t, lead, True, "x")
    assert opinions.clear_votes(t, lead) == 1


# --- vistas ---------------------------------------------------------------------------------------------------------


def test_views_post_only_csrf_and_escaping(client_for, member, lead):
    t = idea(member)
    t.title = "<script>alert(1)</script>"
    t.save()
    c = client_for(lead.login)
    html = c.get(reverse("community:thread", args=[t.pk])).content.decode()
    assert (
        "<script>alert(1)" not in html
        and "Encuesta rápida" in html
        and "Opinar" in html
        or "¿Qué opinas?" in html
    )
    assert c.get(reverse("community:react", args=["thread", t.pk])).status_code == 405
    assert c.get(reverse("community:poll_vote", args=[t.pk])).status_code == 405
    r = c.post(reverse("community:react", args=["thread", t.pk]), {"reaction": "idea"})
    assert r.status_code == 302 and Reaction.objects.count() == 1
    r = c.post(reverse("community:poll_vote", args=[t.pk]), {"option": t.poll_options.first().pk})
    assert r.status_code == 302 and PollVote.objects.count() == 1
    assert c.post(reverse("community:react", args=["bad", t.pk]), {}).status_code == 404
    strict = client_for(lead.login)
    strict.handler.enforce_csrf_checks = True
    assert (
        strict.post(
            reverse("community:react", args=["thread", t.pk]), {"reaction": "tested"}
        ).status_code
        == 403
    )


def test_hidden_thread_404_for_members_on_actions(client_for, member, lead, make_person):
    t = idea(member)
    moderation.set_hidden(t, lead, True, "x")
    other = client_for(make_person("o@lev.cl").login)
    assert (
        other.post(
            reverse("community:react", args=["thread", t.pk]), {"reaction": "idea"}
        ).status_code
        == 404
    )
    assert other.post(reverse("community:poll_vote", args=[t.pk]), {"option": 1}).status_code == 404


def test_clear_opinions_view_leads_only(client_for, member, lead, make_person):
    t = idea(member)
    opinions.toggle_reaction(lead, t, "idea")
    opinions.vote(t, lead, t.poll_options.first().pk)
    moderation.set_hidden(t, lead, True, "x")
    url = reverse("community:clear_opinions", args=[t.pk])
    assert client_for(make_person("m@lev.cl").login).post(url, {"votes": "1"}).status_code == 403
    client_for(lead.login).post(url, {"votes": "1"})
    assert not Reaction.objects.exists() and not PollVote.objects.exists()


def test_sorting_and_summary(client_for, member, lead, make_person):
    thread(member, title="Tranquilo")
    loved = thread(member, title="Querido")
    opinions.toggle_reaction(lead, loved, "idea")
    opinions.toggle_reaction(make_person("z@lev.cl"), loved, "useful")
    forum.reply(loved, lead, "hola")
    c = client_for(lead.login)
    url = reverse("community:forum")
    useful = c.get(url, {"orden": "utiles"})
    titles = [t.title for t in useful.context["page"]]
    assert titles.index("Querido") < titles.index("Tranquilo")
    assert dict(useful.context["page"][0].reaction_summary) == {"👍": 1, "💡": 1}
    none = [t.title for t in c.get(url, {"orden": "sin_respuesta"}).context["page"]]
    assert "Tranquilo" in none and "Querido" not in none
    assert c.get(url, {"orden": "raro"}).status_code == 200


def test_idea_thread_shows_cta_in_list(client_for, member):
    idea(member)
    html = client_for(member.login).get(reverse("community:forum")).content.decode()
    assert "Opinar" in html and "Encuesta" in html


# --- consultas acotadas ---------------------------------------------------------------------------------------------


def _count(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_queries_do_not_grow_with_data(client_for, member, lead, make_person):
    c = client_for(lead.login)
    first = idea(member)
    forum.reply(first, member, "uno")
    list_url, detail_url = reverse("community:forum"), reverse("community:thread", args=[first.pk])
    base_list, base_detail = _count(c, list_url), _count(c, detail_url)
    for i in range(12):
        fan = make_person(f"f{i}@lev.cl")
        t = idea(member, "A\nB")
        post = forum.reply(first, lead, f"msg {i}")
        for kind in ("useful", "idea"):
            opinions.toggle_reaction(fan, t, kind)
            opinions.toggle_reaction(fan, post, kind)
            opinions.toggle_reaction(fan, first, kind)
        opinions.vote(t, fan, t.poll_options.first().pk)
        opinions.vote(first, fan, first.poll_options.first().pk)
    assert _count(c, list_url) <= base_list
    assert _count(c, detail_url) <= base_detail
