import itertools
import json
import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.gamification import avatar as av
from apps.gamification.avatar import engine, palettes
from apps.gamification.avatar.art import GRID, sym
from apps.gamification.avatar.parts import body
from apps.gamification.avatar.validation import SPECS, validate_all, validate_category

STYLE_CATEGORIES = [
    "hair", "eyes", "brows", "mouth", "facial_hair", "glasses", "headwear", "outfit", "neckwear", "legwear", "body",
]  # fmt: skip


# --- las piezas de arte cumplen su contrato --------------------------------------------------------------


@pytest.mark.parametrize("category", list(SPECS))
def test_art_parts_follow_their_contract(category):
    assert validate_category(category) == []


def test_all_parts_validate_together():
    assert validate_all() == []


def test_base_body_fits_the_grid_and_uses_known_keys():
    keys = set()
    for layer in (body.BASE, *body.BODY_PATCH.values(), *body.LEGWEAR.values(), body.NOSE):
        for y, line in layer.items():
            assert 0 <= y < GRID and len(line) == GRID, (y, line)
            keys |= set(line) - {"."}
    assert keys <= set(engine.palette_for(engine.clean_config({}))), keys


def test_sym_mirrors_and_rejects_wrong_widths():
    assert sym("ab" + "." * 14) == "ab" + "." * 14 + "." * 14 + "ba"
    with pytest.raises(ValueError):
        sym("....")


# --- composición y SVG ---------------------------------------------------------------------------------------


def test_compose_is_a_32x32_matrix_and_every_key_has_a_color():
    cfg = engine.clean_config(
        {"hair": "long", "headwear": "cap", "glasses": "round", "facial_hair": "beard"}
    )
    grid = engine.compose(cfg)
    assert len(grid) == GRID and all(len(row) == GRID for row in grid)
    used = {ch for row in grid for ch in row} - {"."}
    assert used <= set(engine.palette_for(cfg))


def test_render_is_a_safe_pixel_svg():
    svg = av.render_svg(av.default_config("ana@lev.cl"), title='Ana <b>"x"</b>')
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'shape-rendering="crispEdges"' in svg and 'viewBox="-2 -2 36 36"' in svg
    assert "<b>" not in svg and "&lt;b&gt;" in svg and "&quot;x&quot;" in svg
    assert "<script" not in svg and "javascript:" not in svg
    assert re.findall(r"<(\w+)", svg).count("path") >= 8  # un path por color


def test_bust_view_crops_head_and_shoulders():
    assert 'viewBox="2 0 28 28"' in av.render_svg({}, view="bust")
    assert 'viewBox="4 2 24 24"' in av.render_svg({}, view="bust", frame=False)


def test_runs_are_merged_so_the_svg_stays_small():
    cfg = {
        "hair": "long",
        "headwear": "cap",
        "glasses": "square",
        "facial_hair": "full_beard",
        "outfit": "hoodie",
    }
    assert len(av.render_svg(cfg)) < 5000


def test_render_is_deterministic():
    cfg = av.default_config("luis@lev.cl")
    assert av.render_svg(cfg) == av.render_svg(dict(cfg))


def test_frame_uses_the_rarity_variable_with_a_fallback():
    assert "var(--rarity-legendary,#E0A800)" in av.render_svg({"frame": "legendary"})
    assert "var(--rarity" not in av.render_svg({"frame": "legendary"}, frame=False)


@pytest.mark.parametrize("bad", [None, {}, {"hair": None}, {"class": "mago"}])
def test_render_tolerates_missing_or_odd_config(bad):
    assert av.render_svg(bad).startswith("<svg")


# --- cada opción cambia algo y se distingue de las demás -------------------------------------------------------


@pytest.mark.parametrize("category", STYLE_CATEGORIES)
def test_every_option_of_a_style_category_looks_different(category):
    base = engine.clean_config({"hair": "short", "hair_color": 5, "skin": 2, "headwear": "none"})
    renders = {}
    for option in engine.CHOICES[category]:
        cfg = {**base, category: option}
        renders[option] = json.dumps(engine.compose(engine.clean_config(cfg)))
    assert len(set(renders.values())) == len(renders), "hay opciones idénticas: " + ", ".join(
        k for k, v in renders.items() if list(renders.values()).count(v) > 1
    )


@pytest.mark.parametrize(
    "category", ["skin", "hair_color", "eye_color", "outfit_color", "pants_color", "background"]
)
def test_every_color_option_changes_the_result(category):
    base = {"hair": "short", "eyes": "iris", "headwear": "none"}
    svgs = {av.render_svg({**base, category: i}) for i in engine.CHOICES[category]}
    assert len(svgs) == len(engine.CHOICES[category])


def test_glasses_and_headwear_colors_change_the_result():
    base = {"glasses": "round", "headwear": "cap"}
    assert len({av.render_svg({**base, "glasses_color": i}) for i in range(5)}) == 5
    assert (
        len(
            {
                av.render_svg({**base, "headwear_color": i})
                for i in range(len(palettes.HEADWEAR_COLORS))
            }
        )
        == 8
    )


def test_the_three_bodies_are_visibly_different():
    renders = {b: av.render_svg({"body": b}) for b in ("masculine", "feminine", "neutral")}
    assert len(set(renders.values())) == 3


def test_hair_color_affects_hair_but_not_the_outfit():
    a = engine.compose(engine.clean_config({"hair": "short", "hair_color": 0}))
    b = engine.compose(engine.clean_config({"hair": "short", "hair_color": 5}))
    assert a == b  # la matriz de claves es igual: el color solo cambia la paleta
    assert (
        engine.palette_for({**engine.DEFAULTS, "hair_color": 0})["H"]
        != engine.palette_for({**engine.DEFAULTS, "hair_color": 5})["H"]
    )
    assert (
        engine.palette_for({**engine.DEFAULTS, "hair_color": 0})["O"]
        == engine.palette_for({**engine.DEFAULTS, "hair_color": 5})["O"]
    )


def test_outfits_only_decorate_clothing_cells(monkeypatch):
    monkeypatch.setitem(engine.OUTFITS, "plain", {})
    plain = engine.compose(engine.clean_config({"outfit": "plain"}))
    for outfit in engine.OUTFITS:
        grid = engine.compose(engine.clean_config({"outfit": outfit}))
        for y in range(GRID):
            for x in range(GRID):
                if plain[y][x] != "O" and not (18 <= y <= 25 and 12 <= x <= 19):
                    assert grid[y][x] == plain[y][x] or plain[y][x] == "O", (outfit, x, y)


def test_every_combination_of_the_main_parts_renders():
    combos = itertools.product(engine.HAIR, engine.HEADWEAR, engine.GLASSES, engine.FACIAL_HAIR)
    count = 0
    for hair, hat, glasses, beard in combos:
        svg = av.render_svg(
            {"hair": hair, "headwear": hat, "glasses": glasses, "facial_hair": beard}
        )
        assert svg.count("<svg") == 1
        count += 1
    assert count == len(engine.HAIR) * len(engine.HEADWEAR) * len(engine.GLASSES) * len(
        engine.FACIAL_HAIR
    )


# --- configuración ---------------------------------------------------------------------------------------------


def test_default_config_is_stable_per_login_and_varied_across_people():
    assert av.default_config("Ana@LEV.cl ") == av.default_config("ana@lev.cl")
    seen = {tuple(sorted(av.default_config(f"p{i}@lev.cl").items())) for i in range(60)}
    assert len(seen) == 60  # el equipo no se ve todo igual


def test_default_config_covers_all_three_bodies():
    bodies = {av.default_config(f"p{i}@lev.cl")["body"] for i in range(30)}
    assert bodies == {"masculine", "feminine", "neutral"}


def test_default_config_never_assigns_locked_pieces():
    for i in range(80):
        cfg = av.default_config(f"p{i}@lev.cl")
        assert cfg["headwear"] not in engine.UNLOCKS["headwear"]
        assert cfg["glasses"] not in engine.UNLOCKS["glasses"]
        assert cfg["frame"] == "common"


def test_default_config_respects_the_chosen_class():
    cfg = av.default_config("x@lev.cl", "pilot")
    assert cfg["class"] == "pilot" and cfg["outfit"] == "flight_jacket"


def test_class_sets_the_starting_outfit_unless_overridden():
    assert av.clean_config({"class": "engineer"})["outfit"] == "hivis_vest"
    assert av.clean_config({"class": "engineer", "outfit": "hoodie"})["outfit"] == "hoodie"


def test_clean_config_drops_unknown_and_unsafe_values():
    cfg = av.clean_config(
        {"class": "mago", "hair": "<script>", "skin": 99, "hair_color": -1, "glasses": {"x": 1},
         "frame": "mythic", "extra": "<script>", "body": ["a"]}
    )  # fmt: skip
    assert cfg == av.DEFAULTS
    assert "extra" not in cfg


def test_clean_config_rejects_booleans_as_indexes():
    cfg = av.clean_config({"skin": True, "hair_color": False})
    assert cfg["skin"] == av.DEFAULTS["skin"] and cfg["hair_color"] == av.DEFAULTS["hair_color"]


def test_locked_pieces_fall_back_unless_the_badge_is_unlocked():
    wanted = {"headwear": "hardhat", "glasses": "goggles", "frame": "epic"}
    locked = av.clean_config(wanted, unlocked=[])
    assert (locked["headwear"], locked["glasses"], locked["frame"]) == ("none", "none", "common")
    ok = av.clean_config(wanted, unlocked=["primer-trofeo", "alas-dgac", "reliquia-bentley"])
    assert (ok["headwear"], ok["glasses"], ok["frame"]) == ("hardhat", "goggles", "epic")
    assert av.clean_config({"headwear": "cap"}, unlocked=[])["headwear"] == "cap"  # libre
    assert av.clean_config(wanted)["headwear"] == "hardhat"  # sin lista no se valida


def test_every_unlock_points_to_a_real_piece_and_a_real_badge():
    badges = json.loads((Path(settings.BASE_DIR) / "seed/insignias.json").read_text("utf-8"))[
        "badges"
    ]
    slugs = {b["slug"] for b in badges}
    for group, pieces in engine.UNLOCKS.items():
        for piece, badge in pieces.items():
            assert badge in slugs, badge
            assert piece in engine.CHOICES[group], (group, piece)


# --- catálogo --------------------------------------------------------------------------------------------------


def test_catalog_lists_every_choice_with_spanish_labels():
    cat = av.catalog()
    for key, allowed in engine.CHOICES.items():
        assert key in cat, key
        assert len(cat[key]) == len(allowed), key
        for option in cat[key]:
            assert str(option["label"]).strip(), (key, option)
    assert {o["id"] for o in cat["body"]} == {"masculine", "feminine", "neutral"}
    assert [o["label"] for o in cat["body"]] == ["Hombre", "Mujer", "Neutro"]


def test_catalog_swatches_have_valid_colors():
    cat = av.catalog()
    for key in (
        "skin",
        "hair_color",
        "eye_color",
        "outfit_color",
        "pants_color",
        "glasses_color",
        "headwear_color",
    ):
        for option in cat[key]:
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", option["color"]), (key, option)


def test_the_palette_offers_real_variety():
    assert len(palettes.SKINS) >= 8 and len(palettes.HAIR_COLORS) >= 12
    assert len(engine.HAIR) >= 14 and len(engine.OUTFITS) >= 10 and len(engine.HEADWEAR) >= 10
