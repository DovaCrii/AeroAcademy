"""Insignias en el avatar (R3): solo la rareza de las insignias públicas de la vitrina, y la persona puede ocultarlas."""

import pytest

from apps.gamification import avatar, game, services
from apps.gamification.avatar import engine
from apps.gamification.models import Badge, PersonBadge

pytestmark = pytest.mark.django_db

EDITOR = "/perfil/avatar/"


@pytest.fixture
def badges(db):
    return {
        rarity: Badge.objects.create(slug=f"b-{rarity}", name=f"Insignia {rarity}", rarity=rarity)
        for rarity in ("common", "rare", "epic", "legendary")
    }


def earn(person, badge):
    PersonBadge.objects.create(person=person, badge=badge)


def test_show_badges_is_a_stored_choice_that_defaults_to_visible():
    assert engine.DEFAULTS["show_badges"] == 1 and list(engine.CHOICES["show_badges"]) == [0, 1]
    assert avatar.clean_config({"show_badges": 0})["show_badges"] == 0
    assert avatar.clean_config({"show_badges": 7})["show_badges"] == 1
    assert avatar.clean_config({"show_badges": True})["show_badges"] == 1
    assert list(engine.CHOICES)[-1] == "show_badges"  # se agregó al final


def test_the_badge_is_the_highest_public_rarity(member, badges):
    cfg = services.person_config(member)
    assert services.avatar_badge(member, cfg) is None
    earn(member, badges["rare"])
    assert services.avatar_badge(member, cfg) == "rare"
    earn(member, badges["epic"])
    earn(member, badges["common"])
    assert services.avatar_badge(member, cfg) == "epic"


def test_retired_badges_do_not_show(member, badges):
    earn(member, badges["legendary"])
    Badge.objects.filter(pk=badges["legendary"].pk).update(retired=True)
    assert services.avatar_badge(member, services.person_config(member)) is None


def test_the_person_can_hide_their_badges(member, badges):
    earn(member, badges["epic"])
    member.avatar_config = {"show_badges": 0}
    member.save()
    assert services.avatar_badge(member, services.person_config(member)) is None


def test_badge_adds_a_sleeve_patch_and_a_helmet_sticker_in_the_rarity_color():
    plain = avatar.render_svg({"headwear": "hardhat"}, view="stage")
    epic = avatar.render_svg({"headwear": "hardhat"}, view="stage", badge="epic")
    legendary = avatar.render_svg({"headwear": "hardhat"}, view="stage", badge="legendary")
    assert plain != epic != legendary
    assert engine.BADGE_COLORS["epic"] in epic and engine.BADGE_COLORS["epic"] not in plain
    # el adhesivo solo va en el casco de obra: con gorra queda el parche de la manga
    cap = avatar.render_svg({"headwear": "cap"}, view="stage", badge="epic")
    assert cap != avatar.render_svg({"headwear": "cap"}, view="stage")
    assert avatar.render_svg({}, view="stage", badge="nope") == avatar.render_svg({}, view="stage")


def test_the_drawing_gets_a_rarity_and_never_a_name(member, badges):
    earn(member, badges["epic"])
    svg = avatar.render_svg(services.person_config(member), view="stage", badge="epic")
    assert "Insignia" not in svg and "b-epic" not in svg


def test_sheet_shows_the_badge_of_whoever_is_viewed_to_everyone(
    client_for, member, make_person, badges
):
    other = make_person("otra@example.com")
    earn(other, badges["legendary"])
    html = client_for(member.login).get(f"/personas/{other.pk}/").content.decode()
    assert engine.BADGE_COLORS["legendary"] in html
    other.avatar_config = {"show_badges": 0}
    other.save()
    html = client_for(member.login).get(f"/personas/{other.pk}/").content.decode()
    assert (
        engine.BADGE_COLORS["legendary"] not in html.split('class="av-frame')[1].split("</svg>")[0]
    )


def test_editor_lets_people_hide_the_badges_and_saves_it(client_for, member, badges):
    earn(member, badges["rare"])
    client = client_for(member.login)
    html = client.get(EDITOR).content.decode()
    assert 'name="show_badges" value="1" checked' in html and 'name="show_badges" value="0"' in html
    assert "Insignias en mi avatar" in html
    client.post(EDITOR, {"show_badges": "0"})
    member.refresh_from_db()
    assert member.avatar_config["show_badges"] == 0
    preview = client.get("/perfil/avatar/vista/", {"show_badges": "1"}).content.decode()
    off = client.get("/perfil/avatar/vista/", {"show_badges": "0"}).content.decode()
    assert preview != off  # con la insignia ocultada el parche desaparece


def test_game_award_flow_unchanged(member):
    assert game.level_info(member)["level"] == 1


@pytest.mark.parametrize("outfit", sorted(engine.OUTFITS))
def test_the_sleeve_patch_shows_with_every_outfit(outfit):
    cfg = {"outfit": outfit}
    assert avatar.render_svg(cfg, view="stage", badge="epic") != avatar.render_svg(
        cfg, view="stage"
    )


@pytest.mark.parametrize("hat", ["hardhat", "hardhat_lamp", "bump_cap"])
def test_helmets_carry_the_sticker_and_other_hats_do_not(hat):
    from apps.gamification.avatar.hd import compose

    def marks(headwear):
        grid = compose.compose_layers(
            engine.clean_config({"headwear": headwear, "outfit": "tshirt"}), "stand", "epic"
        )
        return sum(row[x] == "6" for row in grid[:30] for x in range(64))

    assert marks(hat) > 0 and marks("cap") == 0 and marks("none") == 0
