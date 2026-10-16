"""Figura HD: escenario de 80×80 con la figura de 64×64 (docs/AVATAR_RESOLUCION.md, HD-1)."""

import re
import time
from pathlib import Path

import pytest
from django.conf import settings

from apps.gamification import avatar, services
from apps.gamification.avatar import engine, hd, palettes, views
from apps.gamification.avatar.hd import compose as hd_compose
from apps.gamification.avatar.hd import render as hd_render
from apps.gamification.avatar.parts import poses

pytestmark = pytest.mark.django_db

ROOT = Path(settings.BASE_DIR)
EDITOR = "/perfil/avatar/"
PREVIEW = "/perfil/avatar/vista/"
STAGE = views.STAGE


def mask(grid):
    return {(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch != "."}


# --- escenario y determinismo -----------------------------------------------------------------------------------


def test_stage_hd_is_80_and_deterministic():
    cfg = avatar.default_config("ana@example.com")
    svg = avatar.render_svg(cfg, view="stage")
    assert 'viewBox="0 0 80 80"' in svg and svg == avatar.render_svg(dict(cfg), view="stage")
    assert len(hd_compose.compose_hd(engine.clean_config(cfg))) == STAGE
    assert hd.GRID_HD == 64 and hd.OFFSET == (8, 12)


def test_stage_only_accepts_multiples_of_80(settings):
    cfg = avatar.clean_config({})
    settings.DEBUG = True
    for ok in (80, 160, 240):
        assert f'width="{ok}"' in services.svg_sized(cfg, ok, view="stage")
    with pytest.raises(ValueError):
        services.svg_sized(cfg, 200, view="stage")


def test_stage_figure_sits_inside_the_stage_with_air_above():
    cells = mask(hd_compose.compose_layers(engine.clean_config({"hair": "afro"})))
    xs, ys = [x for x, _ in cells], [y for _, y in cells]
    assert min(xs) >= hd.OFFSET[0] and max(xs) < hd.OFFSET[0] + hd.GRID_HD
    assert min(ys) >= hd.OFFSET[1] and max(ys) < hd.GROUND_Y  # arriba queda aire para antena y dron


def test_stage_has_a_floor_shadow_under_the_boots():
    svg = avatar.render_svg({"background": 0}, view="stage")
    assert f"M24 {hd.GROUND_Y + 1}h32" in svg and 'fill-opacity=".2"' in svg
    light = avatar.render_svg({"background": 18}, view="stage")
    assert 'fill-opacity=".13"' in light


def test_every_path_stays_inside_the_stage():
    svg = avatar.render_svg(avatar.surprise("hd", "cartographer"), view="stage")
    for d in re.findall(r' d="([^"]+)"', svg):
        for x, y, w, h in re.findall(r"M(\d+) (\d+)h(\d+)v(\d+)", d):
            assert int(x) + int(w) <= STAGE and int(y) + int(h) <= STAGE


# --- cada opción se dibuja en HD --------------------------------------------------------------------------------


def test_every_option_renders_in_hd():
    base = engine.clean_config({})
    for key, allowed in engine.CHOICES.items():
        for value in allowed:
            cfg = engine.clean_config({**base, key: value})
            svg = avatar.render_svg(cfg, view="stage")
            assert svg.startswith("<svg") and svg.endswith("</svg>"), (key, value)


def test_hd_without_art_equals_up2_plus_the_finishing_pass(monkeypatch):
    """Sin piezas HD, la figura es la de 32 escalada ×2 (mismas capas y reglas) más el pase de acabado."""
    for category in hd.HD:
        monkeypatch.setitem(hd.HD, category, {})
    for seed in ("a", "b", "c", "d"):
        cfg = avatar.surprise(seed, "")
        low = engine.compose(cfg)
        layers = hd_compose.compose_layers(cfg)
        ox, oy = hd.OFFSET
        for y in range(avatar.GRID):
            for x in range(avatar.GRID):
                block = {layers[oy + 2 * y + dy][ox + 2 * x + dx] for dy in (0, 1) for dx in (0, 1)}
                assert block == {low[y][x]}, (seed, x, y)


def test_hd_matches_low_silhouette():
    """La máscara HD reducida a la mitad coincide con la de 32 (la miniatura y la vista grande cuentan lo mismo)."""
    for seed in range(6):
        cfg = avatar.surprise(f"s{seed}", "")
        low = mask(engine.compose(cfg))
        big = mask(hd_compose.compose_hd(cfg))
        ox, oy = hd.OFFSET
        reduced = {((x - ox) // 2, (y - oy) // 2) for x, y in big if x >= ox and y >= oy}
        assert len(low & reduced) / len(low | reduced) >= 0.7


def test_face_window_is_sacred_in_hd():
    """Ni el pelo ni un gorro dibujan sobre ojos, nariz y boca, con cualquier combinación."""
    for hair in ("afro", "long", "mohawk", "bun"):
        for hat in ("none", "hardhat", "beanie", "explorer"):
            cfg = engine.clean_config({"hair": hair, "headwear": hat, "hair_color": 3})
            bare = engine.clean_config({"hair": "bald", "headwear": "none"})
            a, b = hd_compose.compose_layers(cfg), hd_compose.compose_layers(bare)
            for y in hd_compose.FACE_Y:
                for x in hd_compose.FACE_X:
                    assert a[y][x] == b[y][x], (hair, hat, x, y)


# --- registro HD ------------------------------------------------------------------------------------------------


def test_hd_ids_are_known_options():
    options = {
        "eyes": engine.EYES, "brows": engine.BROWS, "mouth": engine.MOUTHS, "glasses": engine.GLASSES,
        "facial_hair": engine.FACIAL_HAIR, "headwear": engine.HEADWEAR, "hair": engine.HAIR,
        "outfit": engine.OUTFITS, "neckwear": engine.NECKWEAR, "pin": engine.PINS, "prop": engine.PROPS,
    }  # fmt: skip
    assert set(hd.HD) == set(options)
    for category, art in hd.HD.items():
        assert set(art) <= set(options[category]), category


def test_hd_sprites_use_the_palette_and_never_the_engine_keys():
    """Las claves `1..4` (luces) las pone solo el motor: ninguna pieza, de 32 o HD, las dibuja a mano."""
    pieces = []
    for registry in (engine.HAIR, engine.HEADWEAR):
        for art in registry.values():
            pieces += [art["front"], art["back"]]
    for registry in (engine.EYES, engine.BROWS, engine.MOUTHS, engine.GLASSES, engine.FACIAL_HAIR,
                     engine.OUTFITS, engine.NECKWEAR, engine.PROPS, engine.PINS):  # fmt: skip
        pieces += list(registry.values())
    for rows in pieces:
        assert not set("".join(rows.values())) & set("1234")
    palette = hd_render.palette_hd(engine.clean_config({}))
    for category, art in hd.HD.items():
        for option, sprite in art.items():
            for part in sprite.values() if "rows" not in sprite else [sprite]:
                for line in part["rows"]:
                    assert set(line) <= set(palette) | {"."} and not set(line) & set("1234"), (
                        category,
                        option,
                    )


def test_sprite_helper_validates_its_space():
    assert hd.sprite((1, 2), ["K"])["space"] == "figure"
    with pytest.raises(ValueError):
        hd.sprite((0, 0), ["K"], space="otro")


def test_up2_doubles_every_cell():
    assert hd.up2({3: "KS."}) == {6: "KKSS..", 7: "KKSS.."}


def test_a_registered_hd_sprite_replaces_its_layer(monkeypatch):
    cfg = engine.clean_config({"eyes": "dot"})
    base = hd_compose.compose_layers(cfg)
    monkeypatch.setitem(hd.HD["eyes"], "dot", hd.sprite((24, 22), ["EE", "EE"]))
    custom = hd_compose.compose_layers(cfg)
    ox, oy = hd.OFFSET
    assert custom != base and custom[oy + 22][ox + 24] == "E"


# --- rendimiento ------------------------------------------------------------------------------------------------


def test_hd_render_budget():
    sizes, started = [], time.perf_counter()
    for seed in range(8):
        hd_render._stage_body.cache_clear()
        sizes.append(len(avatar.render_svg(avatar.surprise(f"p{seed}", ""), view="stage")))
    per_render = (time.perf_counter() - started) / 8
    assert max(sizes) < 16_000, sizes
    assert per_render < 0.08, (
        per_render
    )  # sin caché; con ella la misma configuración sale al instante


def test_same_configuration_is_served_from_the_cache():
    hd_render._stage_body.cache_clear()
    cfg = avatar.default_config("luis@example.com")
    avatar.render_svg(cfg, view="stage")
    avatar.render_svg(dict(cfg), view="stage", title="Otro título")
    assert hd_render._stage_body.cache_info().hits >= 1


# --- poses (solo vista previa) ----------------------------------------------------------------------------------


def test_poses_change_the_figure_and_stand_is_the_default():
    cfg = engine.clean_config({})
    stand = avatar.render_svg(cfg, view="stage")
    assert stand == avatar.render_svg(cfg, view="stage", pose="stand")
    assert avatar.render_svg(cfg, view="stage", pose="wave") != stand
    assert avatar.render_svg(cfg, view="stage", pose="no-existe") == stand


def test_every_pose_keeps_the_face_and_stays_in_the_arms():
    for name, patch in poses.POSES.items():
        for y, (x, chars) in patch.items():
            assert 8 <= y <= 27 or not patch, name
            assert all(x + i <= 7 or x + i >= 24 for i in range(len(chars))), (name, y)


def test_pose_is_preview_only(member_client, member):
    html = member_client.get(PREVIEW, {"pose": "wave"}).content.decode()
    assert html != member_client.get(PREVIEW).content.decode()
    member_client.post(EDITOR, {"hair": "bun", "pose": "wave", "zoom": "1"})
    member.refresh_from_db()
    assert "pose" not in member.avatar_config and "zoom" not in member.avatar_config
    assert services.valid_pose("<script>") == "stand"


def test_editor_offers_pose_and_zoom_that_are_not_saved(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert 'name="pose" value="stand" checked' in html and 'name="pose" value="wave"' in html
    assert 'name="zoom" id="zoom-3" value="3" checked' in html
    css = (ROOT / "apps/gamification/static/gamification/editor.css").read_text("utf-8")
    assert ":has(#zoom-2:checked)" in css
    js = (ROOT / "apps/core/static/core/enhance.js").read_text("utf-8")
    assert 'query.delete("zoom")' in js


def test_preview_and_sheet_use_the_stage_at_whole_sizes(client_for, member):
    page = client_for(member.login).get(EDITOR).content.decode()
    assert re.search(r'<svg width="240" height="240" viewBox="0 0 80 80"', page)
    sheet = client_for(member.login).get("/perfil/").content.decode()
    assert re.search(r'<svg width="160" height="160" viewBox="0 0 80 80"', sheet)


def test_light_background_in_the_stage_uses_ink_halo():
    assert engine.halo_color(palettes.BACKGROUNDS[18][1]) == engine.HALO_DARK
    assert engine.HALO_DARK in avatar.render_svg({"background": 18}, view="stage")
