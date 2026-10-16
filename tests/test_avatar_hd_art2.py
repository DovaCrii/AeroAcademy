"""HD-6 y HD-7: gorros, ropa, pines y manos HD."""

import pytest

from apps.gamification import avatar
from apps.gamification.avatar import engine, hd
from apps.gamification.avatar.hd import compose as hd_compose
from apps.gamification.avatar.hd import hands
from apps.gamification.avatar.validation import validate_hd

pytestmark = pytest.mark.django_db


def mask(cfg, pose="stand"):
    grid = hd_compose.compose_layers(engine.clean_config(cfg), pose)
    return {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c != "."}


def test_every_hat_outfit_and_pin_has_an_hd_version():
    assert set(hd.HD["headwear"]) == set(engine.HEADWEAR) - {"none"}
    assert set(hd.HD["outfit"]) == set(engine.OUTFITS)
    assert set(hd.HD["pin"]) == set(engine.PINS) - {"none"}
    assert validate_hd(["headwear", "outfit", "pin"]) == []


@pytest.mark.parametrize("hat", sorted(set(engine.HEADWEAR) - {"none"}))
def test_hd_hat_keeps_the_scaled_32_silhouette(monkeypatch, hat):
    """Los detalles solo reemplazan celdas con color: la silueta del gorro es la de siempre ×2."""
    cfg = {"headwear": hat, "hair": "short"}
    with_art = mask(cfg)
    monkeypatch.setitem(hd.HD, "headwear", {})
    assert with_art == mask(cfg)


@pytest.mark.parametrize("outfit", sorted(engine.OUTFITS))
def test_hd_outfit_keeps_the_body_silhouette(monkeypatch, outfit):
    """La ropa solo se pinta sobre el cuerpo (`O`): cambia el detalle, nunca la silueta."""
    cfg = {"outfit": outfit}
    with_art = mask(cfg)
    monkeypatch.setitem(hd.HD, "outfit", {})
    assert with_art == mask(cfg)


def test_hd_details_actually_change_the_pixels(monkeypatch):
    for category, key, ids in (
        ("headwear", "headwear", engine.HEADWEAR),
        ("outfit", "outfit", engine.OUTFITS),
    ):
        for option in ids:
            if option == "none":
                continue
            cfg = engine.clean_config({key: option})
            art = hd_compose.compose_layers(cfg)
            monkeypatch.setitem(hd.HD, category, {})
            plain = hd_compose.compose_layers(cfg)
            monkeypatch.undo()
            assert art != plain, (category, option)


def test_hats_never_cover_the_face_in_hd():
    for hat in set(engine.HEADWEAR) - {"none"}:
        cfg = engine.clean_config({"headwear": hat, "hair": "afro"})
        bare = engine.clean_config({"headwear": "none", "hair": "bald"})
        a, b = hd_compose.compose_layers(cfg), hd_compose.compose_layers(bare)
        for y in hd_compose.FACE_Y:
            for x in hd_compose.FACE_X:
                assert a[y][x] == b[y][x], (hat, x, y)


def test_each_hat_looks_different_in_hd():
    svgs = {avatar.render_svg({"headwear": h}, view="stage") for h in engine.CHOICES["headwear"]}
    assert len(svgs) == len(engine.CHOICES["headwear"])


def test_pins_are_bigger_in_hd_and_sit_on_the_chest():
    for pin in ("compass", "hardhat_pin", "theodolite_pin"):
        art = hd.HD["pin"][pin]
        x, y = art["at"]
        assert len(art["rows"][0]) >= 7 and 36 <= x and y >= 40, pin


def test_wave_pose_draws_an_open_hand():
    assert "wave" in hands.POSE_HANDS
    assert mask({}, "wave") != mask({}, "stand")
    assert hands.GRIP[0] == ".KK." and len(hands.GRIP) == 4  # la mano de las herramientas
