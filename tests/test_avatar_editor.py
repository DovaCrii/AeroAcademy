import pytest
from django.test import Client

from apps.gamification import avatar, services

pytestmark = pytest.mark.django_db

EDITOR = "/perfil/avatar/"
PREVIEW = "/perfil/avatar/vista/"


def post(client, **fields):
    return client.post(EDITOR, fields)


def test_editor_lists_every_category_with_the_current_choice_checked(member_client, member):
    html = member_client.get(EDITOR).content.decode()
    for key in avatar.engine.CHOICES:
        assert f'name="{key}"' in html, key
    cfg = services.person_config(member)
    assert f'name="hair" value="{cfg["hair"]}" checked' in html
    assert "Hombre" in html and "Mujer" in html and "Neutro" in html
    assert "<svg" in html and "Guardar avatar" in html


def test_editor_shows_a_mini_preview_for_every_style_option(member_client):
    html = member_client.get(EDITOR).content.decode()
    for category in services.TILE_CATEGORIES:
        for option in avatar.catalog()[category]:
            assert f'name="{category}" value="{option["id"]}"' in html, (category, option["id"])
    assert html.count('class="tile"') >= 60


def test_saving_persists_the_avatar_and_the_class(client_for, member):
    response = post(
        client_for(member.login),
        body="feminine", skin="4", hair="long", hair_color="8", facial_hair="none", eyes="lashes",
        glasses="round", glasses_color="1", headwear="cap", headwear_color="3", outfit="hoodie",
        outfit_color="6", legwear="skirt", **{"class": "cartographer"},
    )  # fmt: skip
    assert response.status_code == 302 and response.url == EDITOR
    member.refresh_from_db()
    cfg = member.avatar_config
    assert cfg["body"] == "feminine" and cfg["skin"] == 4 and cfg["hair"] == "long"
    assert cfg["hair_color"] == 8 and cfg["glasses"] == "round" and cfg["headwear"] == "cap"
    assert cfg["outfit"] == "hoodie" and cfg["legwear"] == "skirt"
    assert member.character_class == "cartographer" and cfg["class"] == "cartographer"


def test_saved_avatar_is_what_the_editor_shows_next_time(client_for, member):
    client = client_for(member.login)
    post(client, hair="curly", hair_color="9", facial_hair="beard")
    html = client.get(EDITOR).content.decode()
    assert 'name="hair" value="curly" checked' in html
    assert 'name="hair_color" value="9" checked' in html
    assert 'name="facial_hair" value="beard" checked' in html
    assert "Tu avatar quedó guardado" in html


def test_saving_only_changes_the_fields_that_were_sent(client_for, member):
    client = client_for(member.login)
    post(client, hair="bun", skin="6")
    post(client, hair_color="3")
    member.refresh_from_db()
    assert member.avatar_config["hair"] == "bun" and member.avatar_config["skin"] == 6
    assert member.avatar_config["hair_color"] == 3


def test_invalid_values_are_ignored_not_stored(client_for, member):
    post(
        client_for(member.login),
        hair="<script>alert(1)</script>",
        skin="999",
        body="otro",
        frame="mythic",
    )
    member.refresh_from_db()
    assert member.avatar_config["hair"] == avatar.DEFAULTS["hair"]
    assert member.avatar_config["skin"] == avatar.DEFAULTS["skin"]
    assert member.avatar_config["body"] in {"masculine", "feminine", "neutral"}
    assert "<script>" not in str(member.avatar_config)


def test_unknown_fields_are_not_stored(client_for, member):
    post(client_for(member.login), hair="bun", is_staff="1", avatar_url="http://evil.test/x.png")
    member.refresh_from_db()
    assert set(member.avatar_config) == set(avatar.DEFAULTS)
    assert not member.is_staff


def test_locked_pieces_cannot_be_saved_without_the_badge(client_for, member):
    post(client_for(member.login), headwear="hardhat", glasses="goggles", frame="legendary")
    member.refresh_from_db()
    assert member.avatar_config["headwear"] == "none"
    assert member.avatar_config["glasses"] == "none"
    assert member.avatar_config["frame"] == "common"


def test_locked_pieces_show_as_disabled_with_the_badge_name(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert 'name="headwear" value="hardhat" disabled' in html
    assert "Primer Trofeo" in html  # nombre de la insignia que lo desbloquea
    assert (
        'name="headwear" value="cap"' in html and 'name="headwear" value="cap" disabled' not in html
    )


def test_free_pieces_can_be_saved(client_for, member):
    post(client_for(member.login), headwear="cap", glasses="sunglasses", facial_hair="goatee")
    member.refresh_from_db()
    cfg = member.avatar_config
    assert (cfg["headwear"], cfg["glasses"], cfg["facial_hair"]) == ("cap", "sunglasses", "goatee")


def test_avatars_are_personal(client_for, make_person):
    ana, luis = make_person("ana@lev.cl"), make_person("luis@lev.cl")
    post(client_for(ana.login), hair="mohawk", hair_color="10")
    luis.refresh_from_db()
    assert luis.avatar_config == {}
    assert services.person_config(luis) == avatar.clean_config(
        avatar.default_config(luis.login, luis.character_class)
    )


# --- vista previa y atajos ------------------------------------------------------------------------------------------


def test_live_preview_is_a_fragment_and_does_not_save(client_for, member):
    response = client_for(member.login).get(
        PREVIEW, {"hair": "afro", "hair_color": "6", "glasses": "round"}
    )
    html = response.content.decode()
    assert response.status_code == 200 and "<html" not in html
    assert html.count("<svg") == 4  # grande, mediano, pequeño y busto
    assert f"Avatar de {member.name}" in html
    member.refresh_from_db()
    assert member.avatar_config == {}


def test_live_preview_ignores_invalid_values(member_client):
    response = member_client.get(PREVIEW, {"hair": "<b>x</b>", "skin": "-5"})
    assert response.status_code == 200 and "<b>x</b>" not in response.content.decode()


def test_preview_reflects_the_requested_options(member_client):
    plain = member_client.get(PREVIEW, {"headwear": "none"}).content.decode()
    with_cap = member_client.get(PREVIEW, {"headwear": "cap"}).content.decode()
    assert plain != with_cap


def test_random_and_reset_are_unsaved_previews(client_for, member):
    client = client_for(member.login)
    random_page = client.get(EDITOR, {"azar": "1"}).content.decode()
    reset_page = client.get(EDITOR, {"restablecer": "1"}).content.decode()
    assert "Vista previa sin guardar" in random_page and "Vista previa sin guardar" in reset_page
    member.refresh_from_db()
    assert member.avatar_config == {}


def test_random_changes_between_requests(member_client):
    pages = {member_client.get(EDITOR, {"azar": "1"}).content.decode() for _ in range(6)}
    assert len(pages) > 1


def test_random_keeps_my_class_and_never_unlocks_pieces(client_for, member):
    client = client_for(member.login)
    post(client, **{"class": "pilot"})
    for _ in range(8):
        html = client.get(EDITOR, {"azar": "1"}).content.decode()
        assert 'name="class" value="pilot" checked' in html
        assert 'name="headwear" value="hardhat" checked' not in html
        assert 'name="frame" value="legendary" checked' not in html


# --- permisos y cabecera --------------------------------------------------------------------------------------------------


def test_pending_people_cannot_open_or_save(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    client = client_for(pending.login)
    assert client.get(EDITOR).status_code == 302
    assert post(client, hair="bun").status_code == 302
    pending.refresh_from_db()
    assert pending.avatar_config == {}


def test_saving_requires_a_valid_csrf_token(member):
    client = Client(
        enforce_csrf_checks=True, REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login
    )
    assert client.post(EDITOR, {"hair": "bun"}).status_code == 403


def test_only_get_is_allowed_on_the_preview(member_client):
    assert member_client.post(PREVIEW, {"hair": "bun"}).status_code == 405


def test_header_shows_my_avatar_and_links_to_the_editor(member_client, member):
    html = member_client.get("/").content.decode()
    assert 'href="/perfil/avatar/"' in html and "Editar mi avatar" in html
    assert f'aria-label="Avatar de {member.name}"' in html


def test_avatar_tag_escapes_the_name(client_for, member):
    from django.template import Context, Template

    member.display_name = '<script>alert("x")</script>'
    out = Template("{% load avatar_tags %}{% avatar person 32 %}").render(
        Context({"person": member})
    )
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert 'width="32"' in out and 'height="32"' in out


def test_avatar_tag_defaults_to_the_bust_view(member):
    from django.template import Context, Template

    out = Template("{% load avatar_tags %}{% avatar person 48 %}").render(
        Context({"person": member})
    )
    assert 'viewBox="2 0 28 28"' in out
    full = Template('{% load avatar_tags %}{% avatar person 48 "full" %}').render(
        Context({"person": member})
    )
    assert 'viewBox="-2 -2 36 36"' in full


def test_stored_garbage_in_avatar_config_never_breaks_the_page(client_for, member):
    member.avatar_config = {"hair": "no-existe", "skin": "x", "headwear": ["a"]}
    member.save()
    assert client_for(member.login).get("/").status_code == 200
    assert client_for(member.login).get(EDITOR).status_code == 200


def test_non_dict_avatar_config_is_tolerated(client_for, member):
    member.avatar_config = ["no", "es", "un", "dict"]
    member.save()
    assert client_for(member.login).get(EDITOR).status_code == 200
