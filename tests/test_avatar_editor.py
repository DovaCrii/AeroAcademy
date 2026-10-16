import re

import pytest
from django.test import Client

from apps.gamification import avatar, services
from apps.gamification.avatar import careers

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
    assert "<svg" in html and ">Guardar<" in html


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
    ana, luis = make_person("ana@example.com"), make_person("luis@example.com")
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
    assert html.count("<svg") == 2  # la figura y la cabecera
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
    pending = make_person("p@example.com", status="pending")
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


def test_header_shows_my_avatar_and_links_to_my_sheet(member_client, member):
    html = member_client.get("/").content.decode()
    assert 'href="/perfil/"' in html
    assert f'aria-label="Avatar de {member.name}"' in html


def test_avatar_tag_escapes_the_name(client_for, member):
    from django.template import Context, Template

    member.display_name = '<script>alert("x")</script>'
    out = Template("{% load avatar_tags %}{% avatar person 48 %}").render(
        Context({"person": member})
    )
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert 'width="48"' in out and 'height="48"' in out


def test_avatar_tag_defaults_to_the_bust_view(member):
    from django.template import Context, Template

    out = Template("{% load avatar_tags %}{% avatar person 48 %}").render(
        Context({"person": member})
    )
    assert 'viewBox="4 2 24 24"' in out
    full = Template('{% load avatar_tags %}{% avatar person 64 "full" %}').render(
        Context({"person": member})
    )
    assert 'viewBox="0 0 32 32"' in full


def test_stored_garbage_in_avatar_config_never_breaks_the_page(client_for, member):
    member.avatar_config = {"hair": "no-existe", "skin": "x", "headwear": ["a"]}
    member.save()
    assert client_for(member.login).get("/").status_code == 200
    assert client_for(member.login).get(EDITOR).status_code == 200


def test_non_dict_avatar_config_is_tolerated(client_for, member):
    member.avatar_config = ["no", "es", "un", "dict"]
    member.save()
    assert client_for(member.login).get(EDITOR).status_code == 200


# --- estructura del editor: acordeón, resumen y acciones -------------------------------------------------------------


def _details(html):
    return re.findall(r'<details class="av-sec"[^>]*>', html)


def test_every_option_is_reachable(member_client):
    """Nada se quitó del catálogo: cada valor de cada clave sigue siendo un radio del HTML."""
    html = member_client.get(EDITOR).content.decode()
    for key, allowed in avatar.engine.CHOICES.items():
        for value in allowed:
            assert f'name="{key}" value="{value}"' in html, (key, value)


def test_editor_has_six_sections_one_open(member_client):
    html = member_client.get(EDITOR).content.decode()
    sections = _details(html)
    assert [re.search(r'data-slug="([^"]+)"', tag).group(1) for tag in sections] == list(
        services.SECTION_SLUGS
    )
    assert all('name="av-sec"' in tag for tag in sections)
    assert sum(" open" in tag for tag in sections) == 1


def test_editor_opens_the_requested_section(client_for, member):
    client = client_for(member.login)

    def opened(**query):
        html = client.get(EDITOR, query).content.decode()
        return [
            re.search(r'data-slug="([^"]+)"', t).group(1) for t in _details(html) if " open" in t
        ]

    assert opened() == ["carrera"]  # nunca guardó: empieza por la carrera
    assert opened(seccion="pelo") == ["pelo"]
    assert opened(seccion="<script>") == ["carrera"]  # lista cerrada
    post(client, hair="bun")
    assert opened() == ["cuerpo-cara"]
    assert opened(seccion="ropa") == ["ropa"]


def test_saving_returns_to_the_open_section_only_if_it_is_valid(client_for, member):
    client = client_for(member.login)
    assert post(client, hair="bun", seccion="ropa").url == f"{EDITOR}?seccion=ropa"
    assert post(client, hair="bun", seccion="//evil.com").url == EDITOR
    assert post(client, hair="bun").url == EDITOR


def test_dice_and_reset_keep_the_open_section(member_client):
    html = member_client.get(EDITOR, {"seccion": "ropa"}).content.decode()
    assert "?azar=1&amp;seccion=ropa" in html and "?restablecer=1&amp;seccion=ropa" in html
    assert 'name="seccion" id="avSeccion" value="ropa"' in html


def test_cancel_links_to_the_sheet_and_does_not_save(client_for, member):
    client = client_for(member.login)
    html = client.get(EDITOR).content.decode()
    assert re.search(r'<a class="btn ghost" href="/perfil/">Cancelar</a>', html)
    assert "Guardar avatar" not in html and ">Guardar<" in html
    client.get("/perfil/")
    member.refresh_from_db()
    assert member.avatar_config == {}


def test_editor_works_without_js(client_for, member):
    """Todos los radios están en el HTML aunque la sección esté cerrada: el envío no depende de JS."""
    client = client_for(member.login)
    html = client.get(EDITOR, {"seccion": "pelo"}).content.decode()
    form = html[html.index('<form class="av-editor"') :]
    fields = {}
    for tag in re.findall(r"<input[^>]*>", form):
        kind = re.search(r'type="(\w+)"', tag).group(1)
        if kind != "hidden":
            assert " hidden" not in tag and "display:none" not in tag, tag
        if kind == "radio" and " checked" in tag and " disabled" not in tag:
            fields[re.search(r'name="(\w+)"', tag).group(1)] = re.search(
                r'value="([^"]*)"', tag
            ).group(1)
    assert {"pose", "zoom"} <= set(fields)  # controles de la vista previa: no son del catálogo
    fields.pop("pose"), fields.pop("zoom")
    assert set(fields) == set(avatar.engine.CHOICES)  # una elección marcada por cada clave
    assert post(client, **fields).status_code == 302
    member.refresh_from_db()
    assert member.avatar_config["hair"] == fields["hair"]
    assert member.avatar_config["class"] == fields["class"]


def test_summary_shows_the_current_choice(client_for, member):
    client = client_for(member.login)
    post(client, hair="mohawk", hair_color="3", facial_hair="beard")
    member.refresh_from_db()
    cfg = services.person_config(member)
    section = next(s for s in services.SECTIONS if s["slug"] == "pelo")
    summary = services.section_summary(cfg, section)
    assert "Mohicano" in summary and ", " in summary
    html = client.get(EDITOR).content.decode()
    assert f'<span class="av-sum">{summary}</span>' in html
    assert '<span class="av-sum">' in html and html.count('<span class="av-sum">') == 6


def test_every_group_shows_the_chosen_name_in_its_legend(client_for, member):
    client = client_for(member.login)
    post(client, hair="mohawk")
    html = client.get(EDITOR).content.decode()
    assert 'Peinado: <b class="av-cur">Mohicano</b>' in html


def test_career_info_lists_motto_and_bonuses_for_every_career(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert "¿Qué trae cada carrera?" in html and "Lema del oficio" in html
    for data in careers.CAREERS.values():
        assert data["name"] in html and data["title"] in html


def test_recommendation_is_a_dot_with_one_note_per_section(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert "★" not in html and "= recomendado para tu carrera" not in html
    assert html.count("recomendado por tu carrera</p>") >= 3
    assert 'class="rec-dot"' in html


def test_options_have_an_accessible_name_and_a_tooltip(member_client):
    html = member_client.get(EDITOR).content.decode()
    # El nombre accesible va en `aria-label` del radio y el tooltip sale de `data-tip` (CSS puro, sin JS).
    assert 'data-tip="Mohicano"' in html and 'value="mohawk" aria-label="Mohicano"' in html
    assert 'aria-label="Casco de obra: se desbloquea con «Primer Trofeo»"' in html
    assert 'name="headwear" value="hardhat" disabled' in html
