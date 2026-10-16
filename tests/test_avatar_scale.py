"""Escala entera, recortes por zona, silueta (halo), fondos claros y contenedor del marco (docs/AVATAR_REDISENO.md)."""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.template import Context, Template

from apps.gamification import avatar, services
from apps.gamification.avatar import backgrounds, careers, engine, palettes, views
from apps.gamification.avatar.parts import body

pytestmark = pytest.mark.django_db

ROOT = Path(settings.BASE_DIR)
EDITOR = "/perfil/avatar/"
SNAPSHOT = json.loads((Path(__file__).parent / "avatar_choices_snapshot.json").read_text("utf-8"))


# --- escala entera ----------------------------------------------------------------------------------------------


def test_every_view_fits_in_the_grid_and_renders_its_exact_box():
    for name, (x, y, w, h) in views.VIEWS.items():
        assert x >= 0 and y >= 0 and x + w <= avatar.GRID and y + h <= avatar.GRID, name
        assert f'viewBox="{x} {y} {w} {h}"' in avatar.render_svg({}, view=name)


def test_svg_sized_accepts_only_whole_cell_sizes(settings):
    cfg = avatar.clean_config({})
    settings.DEBUG = True
    for view, ok, bad in (
        ("full", 64, 60),
        ("bust", 48, 32),
        ("head", 32, 40),
        ("zone:glasses", 60, 64),
    ):
        assert f'width="{ok}"' in services.svg_sized(cfg, ok, view=view)
        with pytest.raises(ValueError):
            services.svg_sized(cfg, bad, view=view)
    settings.DEBUG = False  # en producción se redondea hacia abajo, sin romper la página
    svg = services.svg_sized(cfg, 40, view="bust")
    assert 'width="24"' in svg and 'height="24"' in svg


def test_height_follows_the_view_aspect():
    svg = services.svg_sized(avatar.clean_config({}), 60, view="zone:glasses")
    assert 'width="60"' in svg and 'height="18"' in svg


def test_avatar_sizes_in_templates_are_integer_multiples():
    """Recorre las plantillas: cada `{% avatar … N "vista" %}` usa un tamaño múltiplo del ancho de la vista."""
    pattern = re.compile(r"\{% avatar \S+ (\d+)(?: \"(\w+)\")?")
    found = 0
    for path in (ROOT / "apps").rglob("*.html"):
        for size, view in pattern.findall(path.read_text("utf-8")):
            found += 1
            assert views.valid_width(view or "bust", int(size)), (path.name, size, view)
    assert found >= 4


def test_every_tile_size_is_a_whole_multiple():
    for key, (view, width) in services.TILE_VIEWS.items():
        assert views.valid_width(view, width), key
    assert views.valid_width(*services.CHIP_VIEW[:1], services.CHIP_VIEW[1])
    for prop in engine.PROPS:
        view, width = services._prop_view(prop)
        assert views.valid_width(view, width), prop


def test_zone_views_contain_the_pieces_they_show():
    def box_of(rows_list):
        cells = [
            (x, y)
            for rows in rows_list
            for y, line in rows.items()
            for x, c in enumerate(line)
            if c != "."
        ]
        return cells

    def inside(view, rows_list):
        x0, y0, w, h = views.box(view)
        return all(x0 <= x < x0 + w and y0 <= y < y0 + h for x, y in box_of(rows_list))

    assert inside("zone:eyes", [*engine.EYES.values(), *engine.BROWS.values()])
    assert inside("zone:glasses", list(engine.GLASSES.values()))
    assert inside("zone:mouth", [*engine.MOUTHS.values(), body.NOSE])
    assert inside("zone:torso", list(engine.OUTFITS.values()))
    assert inside("zone:neck", list(engine.NECKWEAR.values()))
    assert inside("zone:pin", list(engine.PINS.values()))
    assert inside("zone:legs", list(body.LEGWEAR.values()))
    assert inside("head", list(engine.FACIAL_HAIR.values()))


def test_prop_tile_shows_only_the_tool_cropped_to_it():
    cfg = avatar.clean_config({"prop": "prism_pole"})
    view, _width = services._prop_view("prism_pole")
    alone = avatar.render_svg(cfg, view=view, layers="prop")
    full = avatar.render_svg(cfg, view=view)
    assert len(alone) < len(full) and "<path" in alone


# --- peso del editor --------------------------------------------------------------------------------------------


def test_editor_html_size_bounded(member_client):
    html = member_client.get(EDITOR).content.decode()
    # Meta de la adenda: 160 KB. Con 209 miniaturas en línea quedan ~200 KB (con las 7 herramientas nuevas); bajar de ahí pide miniaturas `<img>` cacheables.
    assert len(html.encode()) <= 205_000, len(html.encode())
    assert html.count("<svg") <= 170, html.count("<svg")


# --- silueta ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("index", range(len(palettes.BACKGROUNDS)))
def test_halo_contrast_on_every_background(index):
    color = palettes.BACKGROUNDS[index][1]
    assert engine.contrast(engine.halo_color(color), color) >= 3, palettes.BACKGROUNDS[index][0]


def test_halo_is_one_pixel_outside_the_figure():
    grid = engine.compose(engine.clean_config({}))
    halo = engine.halo_cells(grid)
    assert halo and all(grid[y][x] == "." for x, y in halo)
    near = lambda x, y: any(  # noqa: E731
        0 <= x + dx < 32 and 0 <= y + dy < 32 and grid[y + dy][x + dx] != "."
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    )
    assert all(near(x, y) for x, y in halo)


def test_halo_is_cream_on_dark_and_ink_on_light():
    dark = avatar.render_svg({"background": 0})
    light = avatar.render_svg({"background": 18})
    assert engine.HALO_LIGHT in dark and engine.HALO_DARK in light


def test_zone_crops_and_empty_layers_have_no_halo():
    assert engine.HALO_LIGHT not in avatar.render_svg({}, view="zone:eyes")
    assert engine.HALO_LIGHT not in avatar.render_svg({}, view="zone:bg", layers="none")


# --- fondos claros e índices estables ---------------------------------------------------------------------------


def test_palette_indexes_are_append_only():
    for name, names in SNAPSHOT["palettes"].items():
        assert [entry[0] for entry in getattr(palettes, name)][: len(names)] == names, name


def test_choices_are_append_only():
    for key, saved in SNAPSHOT["choices"].items():
        now = engine.CHOICES[key]
        if isinstance(saved, int):
            assert len(now) >= saved, key
        else:
            assert list(now)[: len(saved)] == saved, key


def test_light_backgrounds_exist_and_are_appended():
    assert len(palettes.BACKGROUNDS) == 24
    for index in range(18, 24):
        base = palettes.BACKGROUNDS[index][1]
        assert engine._luminance(base) > 0.45, palettes.BACKGROUNDS[index][0]
    assert {backgrounds.BY_INDEX[i] for i in (18, 19, 21, 22, 23)} >= {"paper", "sky", "sand"}
    assert 20 not in backgrounds.BY_INDEX  # el kraft es liso


def test_every_career_offers_its_light_background_without_changing_its_look():
    for slug, data in careers.CAREERS.items():
        assert careers.light_background(slug) in data["palette"]["background"], slug
        assert data["look"]["background"] < 18, slug  # el look por defecto sigue siendo el oscuro


def test_stored_backgrounds_still_render_the_same_colors():
    assert palettes.BACKGROUNDS[0] == ("Azul noche", "#0F2A4D")
    assert palettes.BACKGROUNDS[17][0] == "Franja de seguridad"


def test_manual_low_contrast_shows_a_warning(member_client):
    response = member_client.get("/perfil/avatar/vista/", {"outfit_color": "8", "background": "18"})
    assert "La ropa se pierde con este fondo" in response.content.decode()
    ok = member_client.get("/perfil/avatar/vista/", {"outfit_color": "7", "background": "18"})
    assert "La ropa se pierde" not in ok.content.decode()


# --- marco fuera del SVG y fondo automático ---------------------------------------------------------------------


def test_avatar_tag_wraps_the_svg_in_a_frame_container(member):
    member.avatar_config = {"frame": "common"}
    member.save()
    out = Template('{% load avatar_tags %}{% avatar person 96 "full" %}').render(
        Context({"person": member})
    )
    assert out.startswith('<span class="av-frame av-frame--common">') and "var(--rarity" not in out
    bare = Template('{% load avatar_tags %}{% avatar person 32 "head" False %}').render(
        Context({"person": member})
    )
    assert bare.startswith("<svg") and "av-frame" not in bare


def test_preview_has_a_level_plate_outside_the_svg(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert 'class="av-plate" data-nv="1" aria-hidden="true"></span>' in html


def test_new_people_get_a_light_and_a_dark_background_by_theme(member, make_person):
    new = Template('{% load avatar_tags %}{% avatar person 96 "full" %}').render(
        Context({"person": member})
    )
    assert "av-bg-dark" in new and "av-bg-light" in new
    other = make_person("otra@example.com")
    other.avatar_config = {"class": "pilot", "background": 3}
    other.save()
    saved = Template('{% load avatar_tags %}{% avatar person 96 "full" %}').render(
        Context({"person": other})
    )
    assert "av-bg-" not in saved  # lo que se eligió se respeta
    css = (ROOT / "apps/gamification/static/gamification/game.css").read_text("utf-8")
    assert (
        ".av-bg-dark" in css and 'data-theme="dark"' in css and "prefers-color-scheme:dark" in css
    )


# --- «Lo que lleva»: solo para su dueña ------------------------------------------------------------------------


def test_legend_lists_where_each_piece_comes_from(member):
    member.avatar_config = {"class": "cartographer", "prop": "prism_pole", "pin": "hardhat_pin"}
    member.save()
    cfg = services.person_config(member)
    items = services.wearing(cfg, member)
    assert any("de tu oficio" in item for item in items)
    assert all("credencial" not in item.lower() for item in items)


def test_legend_is_visible_only_to_the_owner(client_for, member, make_person):
    other = make_person("otra@example.com")
    mine = client_for(member.login).get("/perfil/").content.decode()
    theirs = client_for(other.login).get(f"/personas/{member.pk}/").content.decode()
    assert "Lo que lleva" in mine and "de tu oficio" in mine
    assert "Lo que lleva" not in theirs and "de tu oficio" not in theirs


# --- vista previa en vivo ---------------------------------------------------------------------------------------


def test_live_preview_never_needs_the_csrf_token_in_the_url():
    js = (ROOT / "apps/core/static/core/enhance.js").read_text("utf-8")
    assert 'query.delete("csrfmiddlewaretoken")' in js and 'query.delete("seccion")' in js


def test_live_preview_ignores_extra_fields(member_client):
    html = member_client.get(
        "/perfil/avatar/vista/", {"csrfmiddlewaretoken": "secreto", "seccion": "x", "hair": "bun"}
    ).content.decode()
    assert "secreto" not in html
