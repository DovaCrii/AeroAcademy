"""Pelo HD (fase 2) y pose «Trabajando»: registro, silueta, colores, combinaciones y selector de poses."""

import itertools

import pytest

from apps.gamification import avatar, services
from apps.gamification.avatar import engine, hd, palettes
from apps.gamification.avatar.hd import compose as hd_compose
from apps.gamification.avatar.hd import hair as hd_hair
from apps.gamification.avatar.hd import hands
from apps.gamification.avatar.hd import render as hd_render
from apps.gamification.avatar.parts import poses
from apps.gamification.avatar.validation import validate_hd

pytestmark = pytest.mark.django_db

EDITOR = "/perfil/avatar/"
PREVIEW = "/perfil/avatar/vista/"
OX, OY = hd.OFFSET
STYLES = sorted(set(engine.HAIR) - {"bald"})
HAIR_KEYS = set("Hhj")


def layers(cfg, **kw):
    return hd_compose.compose_layers(engine.clean_config(cfg), **kw)


def as_hair(grid):
    """La figura con los tres tonos del pelo vistos como uno: lo que importa es qué celdas cubre y de qué es."""
    return [["H" if ch in HAIR_KEYS else ch for ch in row] for row in grid]


def without_hair_art(monkeypatch):
    monkeypatch.setitem(hd.HD, "hair", {})


# --- registro y contrato ----------------------------------------------------------------------------------------


def test_every_hairstyle_has_an_hd_version_except_bald():
    assert set(hd.HD["hair"]) == set(engine.HAIR) - {"bald"}
    assert set(hd.HD["hair"]) <= set(engine.CHOICES["hair"])
    assert "bald" in engine.CHOICES["hair"] and len(STYLES) == 16


def test_hair_pieces_validate_and_stay_in_the_zone():
    assert validate_hd(["hair"]) == []
    x0, y0, x1, y1 = hd.ZONES["hair"]
    for option, art in hd.HD["hair"].items():
        assert set(art) == {"front", "back"}, option
        for layer, piece in art.items():
            if piece is None:
                continue
            ax, ay = piece["at"]
            assert x0 <= ax and y0 <= ay, (option, layer)
            assert ax + len(piece["rows"][0]) - 1 <= x1 and ay + len(piece["rows"]) - 1 <= y1, (
                option,
                layer,
            )


def test_back_layer_exists_exactly_where_the_32_piece_has_one():
    for option in STYLES:
        for layer in ("front", "back"):
            has_low = any(ch != "." for line in engine.HAIR[option][layer].values() for ch in line)
            assert (hd.HD["hair"][option][layer] is not None) == has_low, (option, layer)


def test_hair_uses_only_the_three_hair_tones_and_the_outline():
    for option, art in hd.HD["hair"].items():
        for piece in art.values():
            if piece:
                used = {ch for line in piece["rows"] for ch in line} - {"."}
                assert used <= {"K", "H", "h", "j"}, (option, used)


def test_hair_art_is_deterministic():
    again = hd_hair._style("wavy", hd_hair.STYLES["wavy"])
    assert again == hd.HD["hair"]["wavy"]
    cfg = {"hair": "braids", "hair_color": 4}
    assert avatar.render_svg(cfg, view="stage") == avatar.render_svg(dict(cfg), view="stage")


# --- silueta y paridad con el 32 --------------------------------------------------------------------------------


@pytest.mark.parametrize("option", STYLES)
def test_hd_hair_keeps_the_scaled_32_silhouette(monkeypatch, option):
    """El pelo HD solo cambia el tono de celdas que ya eran pelo: la silueta es la de la pieza de 32 ×2."""
    cfg = {"hair": option, "hair_color": 2}
    with_art = as_hair(layers(cfg))
    without_hair_art(monkeypatch)
    assert with_art == as_hair(layers(cfg))


def test_hd_hair_has_real_detail_not_just_blocks(monkeypatch):
    """Cada peinado tiene más celdas de luz y sombra que su versión ×2, y no son bloques de 2×2."""
    for option in STYLES:
        cfg = {"hair": option, "hair_color": 2}
        art = layers(cfg)
        flat = [ch for row in art for ch in row if ch in "hj"]
        monkeypatch.setitem(hd.HD, "hair", {})
        plain = layers(cfg)
        monkeypatch.undo()
        assert art != plain, option
        assert len(set(flat)) == 2 and len(flat) >= 20, option  # hay luz y sombra de verdad


def test_hair_never_covers_the_face_or_pokes_above_a_hat_in_hd():
    for option, hat in itertools.product(STYLES, engine.CHOICES["headwear"]):
        cfg = {"hair": option, "headwear": hat, "hair_color": 3, "glasses": "sunglasses"}
        bare = {"hair": "bald", "headwear": hat, "hair_color": 3, "glasses": "sunglasses"}
        a, b = layers(cfg), layers(bare)
        for y in hd_compose.FACE_Y:
            for x in hd_compose.FACE_X:
                assert a[y][x] == b[y][x], (option, hat, x, y)
        top = engine._hat_top(engine.HEADWEAR[hat])
        if top is not None:
            limit = OY + top * hd.SCALE
            above = [
                (x, y)
                for y, row in enumerate(a[:limit])
                for x, ch in enumerate(row)
                if ch in HAIR_KEYS
            ]
            assert not above, (option, hat, above[:3])


def test_audit_of_collisions_holds_in_hd_for_every_combination(monkeypatch):
    """Pelo × gorro × lentes × barba: el pelo HD cubre las mismas celdas que el de 32 en cada combinación (así la
    auditoría de choques de `audit.py`, que mira el 32, vale también para la figura grande)."""
    hairs, hats = STYLES, list(engine.CHOICES["headwear"])
    glasses, beards = list(engine.CHOICES["glasses"]), list(engine.CHOICES["facial_hair"])
    combos = (
        [  # cada par pelo × gorro con lentes y barba rotando; y cada pelo × lentes × barba sin gorro
            {
                "hair": h,
                "headwear": t,
                "glasses": glasses[i % len(glasses)],
                "facial_hair": beards[i % len(beards)],
            }
            for i, (h, t) in enumerate(itertools.product(hairs, hats))
        ]
        + [
            {"hair": h, "headwear": "none", "glasses": g, "facial_hair": f}
            for h, g, f in itertools.product(hairs, glasses, beards)
        ]
    )
    expected = []
    for combo in combos:
        expected.append(as_hair(layers({**combo, "hair_color": 1})))
    without_hair_art(monkeypatch)
    for combo, grid in zip(combos, expected, strict=True):
        assert grid == as_hair(layers({**combo, "hair_color": 1})), combo


# --- cada opción y cada color se ven distintos -------------------------------------------------------------------


def test_each_hairstyle_looks_different_in_hd():
    svgs = {avatar.render_svg({"hair": option}, view="stage") for option in engine.CHOICES["hair"]}
    assert len(svgs) == len(engine.CHOICES["hair"])


def test_hairstyles_differ_from_each_other_in_the_hair_pixels_too():
    """Aunque dos peinados compartan silueta parecida, sus píxeles de pelo no son iguales."""
    grids = {
        option: tuple(map(tuple, layers({"hair": option}))) for option in engine.CHOICES["hair"]
    }
    assert len(set(grids.values())) == len(grids)


@pytest.mark.parametrize("option", STYLES)
def test_each_hair_color_changes_the_svg(option):
    svgs = {
        avatar.render_svg({"hair": option, "hair_color": color}, view="stage")
        for color in range(len(palettes.HAIR_COLORS))
    }
    assert len(svgs) == len(palettes.HAIR_COLORS)


def test_hair_tones_come_from_the_chosen_hair_color():
    for color, (_, tones) in enumerate(palettes.HAIR_COLORS):
        svg = avatar.render_svg({"hair": "wavy", "hair_color": color}, view="stage")
        assert all(tone in svg for tone in tones.values()), color


# --- peso -------------------------------------------------------------------------------------------------------


def test_hd_hair_stays_within_the_svg_budget():
    sizes = {}
    for option in engine.CHOICES["hair"]:
        hd_render._stage_body.cache_clear()
        sizes[option] = len(
            avatar.render_svg({"hair": option, "hair_color": 2, "headwear": "none"}, view="stage")
        )
    assert max(sizes.values()) < 8_000, sizes
    assert sum(sizes.values()) / len(sizes) < 6_500, sizes  # la media del doc es 4,9 KB sin pelo HD


# --- pose «Trabajando» -------------------------------------------------------------------------------------------


def test_work_pose_has_a_label_and_the_default_pose_is_unchanged():
    assert list(poses.LABELS_POSES) == ["stand", "wave", "work"]
    assert poses.LABELS_POSES["work"] == "Trabajando" and set(poses.POSES) == set(
        poses.LABELS_POSES
    )
    assert poses.DEFAULT_POSE == services.POSE_DEFAULT == "stand" and "work" in hands.POSE_FRONT
    assert services.valid_pose("work") == "work" and services.valid_pose("<script>") == "stand"


@pytest.mark.parametrize("slug", sorted(engine.CLASSES))
@pytest.mark.parametrize("body", ["masculine", "feminine", "neutral"])
def test_work_pose_renders_for_every_career_and_body_without_cutting_the_gear(slug, body):
    cfg = engine.clean_config({**engine.apply_career({}, slug), "body": body})
    stand = hd_compose.compose_layers(cfg, "stand")
    work = hd_compose.compose_layers(cfg, "work")
    changed = {
        (x, y) for y in range(len(work)) for x in range(len(work)) if work[y][x] != stand[y][x]
    }
    assert changed, slug
    # solo cambia el brazo izquierdo y el antebrazo sobre la cintura: el equipo y el brazo derecho quedan intactos
    assert all(OX + 8 <= x <= OX + 38 and OY + 40 <= y <= OY + 56 for x, y in changed), sorted(
        changed
    )[:4]
    for y in hd_compose.FACE_Y:
        for x in hd_compose.FACE_X:
            assert work[y][x] == stand[y][x]
    svg = avatar.render_svg(cfg, view="stage", pose="work")
    assert 'viewBox="0 0 80 80"' in svg and svg != avatar.render_svg(cfg, view="stage")


def test_work_pose_keeps_the_right_arm_and_tool_whole():
    cfg = engine.clean_config(engine.apply_career({}, "cartographer"))
    stand, work = hd_compose.compose_layers(cfg, "stand"), hd_compose.compose_layers(cfg, "work")
    for y in range(len(work)):
        for x in range(OX + 39, len(work)):  # todo lo que queda a la derecha de la mano de la pose
            assert work[y][x] == stand[y][x], (x, y)


def test_work_pose_is_preview_only_and_the_editor_offers_the_three_poses(member_client, member):
    html = member_client.get(EDITOR).content.decode()
    assert 'name="pose" value="stand" checked' in html
    assert 'name="pose" value="wave"' in html and 'name="pose" value="work"' in html
    assert "Trabajando" in html and html.index('value="stand"') < html.index(
        'value="wave"'
    ) < html.index('value="work"')
    assert (
        member_client.get(PREVIEW, {"pose": "work"}).content != member_client.get(PREVIEW).content
    )
    member_client.post(EDITOR, {"hair": "bun", "pose": "work", "zoom": "1"})
    member.refresh_from_db()
    assert "pose" not in member.avatar_config


def test_every_pose_front_sprite_stays_below_the_chest_and_off_the_face():
    for name, art in hands.POSE_FRONT.items():
        ax, ay = art["at"]
        assert ay >= 40 and ax >= 8 and ax + len(art["rows"][0]) <= 48, name
        used = {ch for line in art["rows"] for ch in line} - {"."}
        assert used <= set("KSsOo"), (name, used)
