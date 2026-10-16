"""Miniaturas `<img>` del editor: endpoint `avatar_piece` (SVG cacheable que solo depende de la URL)."""

import re

import pytest

from apps.gamification import avatar, services
from apps.gamification.avatar import engine

pytestmark = pytest.mark.django_db

EDITOR = "/perfil/avatar/"


def piece(client, key, option, code=None, **extra):
    code = code if code is not None else services.encode_cfg(avatar.clean_config({}))
    return client.get(f"/perfil/avatar/pieza/{key}/{option}/", {"c": code, **extra})


def test_config_code_round_trips_every_choice():
    for seed in ("a", "b", "c", "d", "e"):
        cfg = avatar.surprise(seed, "")
        assert services.decode_cfg(services.encode_cfg(cfg)) == cfg
    assert len(services.encode_cfg(avatar.clean_config({}))) == len(engine.CHOICES)


def test_garbled_code_falls_back_to_the_default():
    default = avatar.clean_config({})
    for garbage in ("", "###", "zzzzzzzzzzzzzzzzzzzzzzzzzz", None, "<script>"):
        assert services.decode_cfg(garbage) == default


def test_endpoint_serves_a_cacheable_svg_for_every_tile(member_client):
    cfg = avatar.default_config("ana@example.com")
    code = services.encode_cfg(cfg)
    for key in services.PIECE_KEYS:
        for option in list(engine.CHOICES[key])[:3]:
            response = piece(member_client, key, option, code)
            assert response.status_code == 200, (key, option)
            assert response["Content-Type"] == "image/svg+xml"
            assert "max-age" in response["Cache-Control"] and "private" in response["Cache-Control"]
            body = response.content.decode()
            assert body.startswith("<svg") and 'xmlns="http://www.w3.org/2000/svg"' in body
            width, height = services.piece_size(key, option)
            assert f'width="{width}"' in body and f'height="{height}"' in body


def test_endpoint_matches_the_service_and_is_deterministic(member_client):
    cfg = avatar.clean_config({"hair": "afro", "skin": 4})
    code = services.encode_cfg(cfg)
    first = piece(member_client, "hair", "bun", code).content.decode()
    assert first == piece(member_client, "hair", "bun", code).content.decode()
    assert first == services.piece_svg(services.decode_cfg(code), "hair", "bun")
    assert (
        first
        != piece(
            member_client, "hair", "bun", services.encode_cfg(avatar.clean_config({"skin": 1}))
        ).content.decode()
    )


@pytest.mark.parametrize(
    ("key", "option"),
    [
        ("hair", "no-existe"),
        ("nope", "bun"),
        ("frame", "rare"),
        ("skin", "1"),
        ("hair", "<script>"),
        ("prop", "../x"),
    ],
)
def test_unknown_categories_and_options_are_404(member_client, key, option):
    assert piece(member_client, key, option).status_code == 404


def test_only_get_and_only_for_approved_people(member_client, client_for, make_person):
    assert member_client.post("/perfil/avatar/pieza/hair/bun/", {}).status_code == 405
    pending = make_person("p@example.com", status="pending")
    assert piece(client_for(pending.login), "hair", "bun").status_code == 302


def test_the_svg_never_carries_text_from_the_url(member_client):
    body = piece(member_client, "hair", "bun", code="<script>alert(1)</script>").content.decode()
    assert "<script" not in body and "alert" not in body


def test_editor_uses_lazy_img_tiles_with_whole_sizes(member_client):
    html = member_client.get(EDITOR).content.decode()
    tags = re.findall(r'<img src="/perfil/avatar/pieza/[^"]+"[^>]*>', html)
    assert len(tags) >= 120
    assert all('loading="lazy"' in t and 'alt=""' in t for t in tags)
    for src, w, h in re.findall(
        r'<img src="(/perfil/avatar/pieza/[^"]+)" width="(\d+)" height="(\d+)"', html
    ):
        key, option = src.split("/pieza/")[1].split("/")[:2]
        assert services.piece_size(key, option) == (int(w), int(h))


def test_every_option_is_still_reachable_with_img_tiles(member_client):
    html = member_client.get(EDITOR).content.decode()
    for key, allowed in engine.CHOICES.items():
        for value in allowed:
            assert f'name="{key}" value="{value}"' in html, (key, value)
