"""Arte HD por tandas: que cada pieza tenga su versión, que respete el contrato y que el peso siga dentro del presupuesto."""

import pytest

from apps.gamification import avatar
from apps.gamification.avatar import engine, hd
from apps.gamification.avatar.hd import compose as hd_compose
from apps.gamification.avatar.hd import render as hd_render
from apps.gamification.avatar.validation import validate_hd

pytestmark = pytest.mark.django_db

OX, OY = hd.OFFSET
EYE_BOX = [(OX + x, OY + y) for x in range(23, 41) for y in range(21, 27)]


def cells(cfg, **kw):
    return {
        (x, y)
        for y, row in enumerate(hd_compose.compose_layers(engine.clean_config(cfg), **kw))
        for x, c in enumerate(row)
        if c != "."
    }


def without_hd(monkeypatch, *categories):
    for category in categories:
        monkeypatch.setitem(hd.HD, category, {})


# --- HD-2: cara ------------------------------------------------------------------------------------------------------


def test_every_face_option_has_an_hd_version():
    assert set(hd.HD["eyes"]) == set(engine.EYES)
    assert set(hd.HD["mouth"]) == set(engine.MOUTHS)
    assert set(hd.HD["brows"]) == set(engine.BROWS) - {"none"}
    assert set(hd.HD["nose"]) == {"default"}


@pytest.mark.parametrize("category", ["eyes", "brows", "mouth"])
def test_each_face_piece_looks_different_from_the_others(category):
    key = {"eyes": "eyes", "brows": "brows", "mouth": "mouth"}[category]
    svgs = {avatar.render_svg({key: option}, view="stage") for option in engine.CHOICES[key]}
    assert len(svgs) == len(engine.CHOICES[key])


def test_hd_face_is_bigger_than_the_scaled_32_version(monkeypatch):
    """Un ojo HD de 5×6 celdas dibuja más píxeles que el de 2×2 escalado."""
    cfg = {"eyes": "dot"}

    def dark(grid):
        return sum(row.count("E") for row in grid)

    hd_dark = dark(hd_compose.compose_layers(engine.clean_config(cfg)))
    without_hd(monkeypatch, "eyes")
    assert hd_dark > dark(hd_compose.compose_layers(engine.clean_config(cfg)))


@pytest.mark.parametrize("category", ["eyes", "brows", "mouth", "nose"])
def test_hd_face_keeps_the_head_silhouette(monkeypatch, category):
    """La cara está dentro de la cabeza: no cambia la silueta de la figura."""
    cfg = avatar.surprise("silueta", "")
    full = cells(cfg)
    without_hd(monkeypatch, category)
    assert full == cells(cfg)


def test_symmetric_pairs_are_centered_on_the_face():
    for category, options in (
        ("eyes", engine.EYES),
        ("brows", engine.BROWS),
        ("glasses", engine.GLASSES),
    ):
        for option in options:
            art = hd.HD[category].get(option)
            if art is None or option in {"wink", "monocle", "fpv"}:
                continue  # el guiño y el monóculo no son simétricos; el visor ya es una sola pieza
            ox, _ = art["at"]
            width = len(art["rows"][0])
            assert ox + width - 1 == 63 - ox, (category, option)  # centrado en x 31,5


# --- HD-3: lentes y barba --------------------------------------------------------------------------------------------


def test_every_glasses_and_beard_option_has_an_hd_version():
    assert set(hd.HD["glasses"]) == set(engine.GLASSES) - {"none"}
    assert set(hd.HD["facial_hair"]) == set(engine.FACIAL_HAIR) - {"none"}


def test_glasses_and_beards_look_different_in_hd():
    for key in ("glasses", "facial_hair"):
        svgs = {avatar.render_svg({key: option}, view="stage") for option in engine.CHOICES[key]}
        assert len(svgs) == len(engine.CHOICES[key])


def test_clear_glasses_let_the_eyes_show_and_opaque_ones_cover_them():
    def eye_pixels(glasses):
        grid = hd_compose.compose_layers(engine.clean_config({"glasses": glasses, "eyes": "dot"}))
        return sum(grid[y][x] == "E" for x, y in EYE_BOX)

    for clear in ("round", "square", "aviator", "safety", "monocle"):
        assert eye_pixels(clear) > 0, clear
    for opaque in ("sunglasses", "fpv"):
        assert eye_pixels(opaque) == 0, opaque


def test_goggles_paint_their_own_eyes_inside():
    grid = hd_compose.compose_layers(engine.clean_config({"glasses": "goggles"}))
    assert sum(grid[y][x] == "E" for x, y in EYE_BOX) > 0 and engine.OPAQUE_GLASSES >= {"goggles"}


def test_beard_goes_behind_the_mouth():
    cfg = {"facial_hair": "full_beard", "mouth": "grin"}
    grid = hd_compose.compose_layers(engine.clean_config(cfg))
    assert any(grid[y][x] == "W" for y in range(OY + 28, OY + 34) for x in range(OX + 26, OX + 38))


def test_hd_pieces_validate_and_stay_within_their_zones():
    assert validate_hd() == []


# --- presupuesto -----------------------------------------------------------------------------------------------------


def test_hd_face_art_stays_within_the_svg_budget():
    cfg = {
        "eyes": "lashes", "mouth": "open", "brows": "thick", "glasses": "goggles", "facial_hair": "full_beard",
        "hair": "afro", "headwear": "hardhat_lamp" if False else "cap", "outfit": "hivis_vest",
    }  # fmt: skip
    hd_render._stage_body.cache_clear()
    assert len(avatar.render_svg(cfg, view="stage")) < 16_000
