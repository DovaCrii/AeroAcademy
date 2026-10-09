import importlib
import json
from pathlib import Path

import pytest
from django.conf import settings

from apps.accounts.models import CharacterClass
from apps.gamification import avatar, services, sheet
from apps.gamification.avatar import audit, backgrounds, careers, engine, palettes
from apps.gamification.avatar.art import GRID
from apps.gamification.avatar.validation import validate_all

pytestmark = pytest.mark.django_db
EDITOR = "/perfil/avatar/"
SEED = Path(settings.BASE_DIR) / "seed"


def test_there_are_many_careers_with_the_original_slugs_kept():
    assert 8 <= len(careers.CAREERS) <= 14
    assert set(careers.LEGACY_SLUGS) <= set(careers.CAREERS)
    assert "lev_lead" in careers.CAREERS
    assert set(CharacterClass.values) == set(careers.CAREERS) == set(avatar.CLASSES)
    for slug, label in CharacterClass.choices:
        assert label == careers.CAREERS[slug]["name"]
        assert len(slug) <= 14


def test_every_career_is_complete_and_points_to_real_pieces():
    attrs = {code for code, _ in sheet.ATTRIBUTES}
    for slug, data in careers.CAREERS.items():
        assert data["discipline"] in careers.DISCIPLINE_LABELS, slug
        assert data["name"] and data["title"] and data["tagline"], slug
        assert set(data["bonus"]) <= attrs and data["bonus"], slug
        look = data["look"]
        assert look["outfit"] in engine.OUTFITS and look["prop"] in engine.PROPS, slug
        assert look["headwear"] in engine.HEADWEAR and look["glasses"] in engine.GLASSES, slug
        assert look["neckwear"] in engine.NECKWEAR, slug
        for key in ("outfits", "headwear", "glasses", "props"):
            category = {"outfits": engine.OUTFITS, "props": engine.PROPS}.get(
                key, getattr(engine, key.upper())
            )
            assert all(p in category for p in data[key]), (slug, key)
        pal = data["palette"]
        assert all(i < len(palettes.OUTFIT_COLORS) for i in pal["outfit_color"])
        assert all(i < len(palettes.HEADWEAR_COLORS) for i in pal["headwear_color"])
        assert all(i < len(palettes.PANTS_COLORS) for i in pal["pants_color"])
        assert all(i < len(palettes.BACKGROUNDS) for i in pal["background"])


@pytest.mark.parametrize("slug", list(careers.CAREERS))
def test_each_career_renders_its_own_look(slug):
    cfg = avatar.apply_career({"hair": "short"}, slug)
    assert cfg["class"] == slug and cfg["outfit"] == careers.CAREERS[slug]["look"]["outfit"]
    svg = avatar.render_svg(cfg)
    assert svg.startswith("<svg") and "<script" not in svg
    grid = engine.compose(cfg)
    assert len(grid) == GRID and all(len(r) == GRID for r in grid)


def test_careers_do_not_all_look_the_same():
    renders = {avatar.render_svg(avatar.apply_career({}, s)) for s in careers.CAREERS}
    assert len(renders) == len(careers.CAREERS)


def test_careers_with_locked_pieces_fall_back_without_the_badge():
    cfg = avatar.apply_career({}, "engineer", unlocked=[])
    assert cfg["headwear"] not in engine.UNLOCKS["headwear"]


def test_new_art_pieces_validate_and_fit_together():
    assert validate_all() == []
    assert audit.run_all() == []


def test_props_stay_beside_the_body_and_off_the_face():
    xs, ys = engine.FACE_X, engine.FACE_Y
    for pid, rows in engine.PROPS.items():
        for y, line in rows.items():
            for x, ch in enumerate(line):
                if ch != ".":
                    assert not (x in xs and y in ys), (pid, x, y)
                    assert x <= 8 or x >= 23, (pid, x, y)


def test_option_counts_meet_the_brief():
    assert len(engine.HAIR) >= 8 and len(engine.GLASSES) - 1 >= 4
    assert len(engine.OUTFITS) >= 15 and len(engine.PROPS) - 1 >= 5
    assert len(engine.HEADWEAR) >= 12 and len(engine.FACIAL_HAIR) >= 6
    assert set(backgrounds.BY_INDEX.values()) >= {"blueprint", "contour", "road", "gears", "hud"}


@pytest.mark.parametrize("index", sorted(backgrounds.BY_INDEX))
def test_patterned_backgrounds_render_and_differ(index):
    plain = avatar.render_svg({"background": 0})
    svg = avatar.render_svg({"background": index})
    assert svg != plain and svg.count("<path") > plain.count("<path")


# --- «Sorpréndeme» ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("slug", list(careers.CAREERS))
def test_surprise_always_gives_a_valid_coherent_combo(slug):
    seen = set()
    for i in range(60):
        cfg = avatar.surprise(f"{slug}-{i}", slug, unlocked=[])
        assert avatar.clean_config(cfg, unlocked=[]) == cfg  # nada inválido ni bloqueado
        data = careers.CAREERS[slug]
        assert cfg["class"] == slug and cfg["outfit"] in data["outfits"]
        assert cfg["prop"] in data["props"] and cfg["glasses"] in data["glasses"]
        assert cfg["outfit_color"] in data["palette"]["outfit_color"]
        assert cfg["background"] in data["palette"]["background"]
        assert engine.outfit_stands_out(cfg), (slug, i)
        assert cfg["headwear"] not in engine.UNLOCKS["headwear"]
        assert avatar.render_svg(cfg).startswith("<svg")
        seen.add(json.dumps(cfg, sort_keys=True))
    assert len(seen) > 40  # de verdad sorprende


def test_surprise_is_deterministic_per_seed_and_picks_a_career_if_none():
    assert avatar.surprise("x", "pilot") == avatar.surprise("x", "pilot")
    assert avatar.surprise("y")["class"] in careers.CAREERS


def test_every_career_default_look_stands_out_from_its_background():
    for slug in careers.CAREERS:
        assert engine.outfit_stands_out(avatar.apply_career({}, slug)), slug


# --- migraciones ------------------------------------------------------------------------------------------------------


def test_data_migration_keeps_old_values_and_clears_unknown_ones(make_person):
    mod = importlib.import_module("apps.accounts.migrations.0006_careers_data")
    from django.apps import apps

    old = make_person("viejo@lev.cl")
    old.character_class = "cartographer"
    old.avatar_config = {"hair": "bun", "class": "pilot"}
    old.save()
    ghost = make_person("fantasma@lev.cl")
    type(ghost).objects.filter(pk=ghost.pk).update(character_class="mago")
    mod.normalize(apps, None)
    old.refresh_from_db()
    ghost.refresh_from_db()
    assert old.character_class == "cartographer" and old.avatar_config["class"] == "cartographer"
    assert old.avatar_config["hair"] == "bun"
    assert ghost.character_class == ""


def test_old_class_slugs_still_open_the_editor(client_for, member):
    for slug in careers.LEGACY_SLUGS:
        member.character_class = slug
        member.avatar_config = {}
        member.save()
        assert client_for(member.login).get(EDITOR).status_code == 200


# --- editor ------------------------------------------------------------------------------------------------------------


def test_editor_groups_careers_by_discipline(member_client):
    html = member_client.get(EDITOR).content.decode()
    for _slug, label in careers.DISCIPLINES:
        assert f"<h3>{label}</h3>" in html
    order = [html.index(f"<h3>{label}</h3>") for _s, label in careers.DISCIPLINES]
    assert order == sorted(order)
    for slug in careers.CAREERS:
        assert f'name="class" value="{slug}"' in html
    # cada carrera con su nombre real, su título de juego y sus bonos
    assert "Líder de Levantamiento Digital" in html and "Gran Maestre del Levantamiento" in html
    assert "Geomensor/a" in html and "CAP +2" in html


def test_career_thumbnails_show_each_careers_own_outfit(member, member_client):
    cfg = services.person_config(member)
    sections = services.editor_sections(cfg, member)
    group = next(g for s in sections for g in s["groups"] if g.get("careers"))
    svgs = [o["svg"] for c in group["clusters"] for o in c["options"]]
    assert len(svgs) == len(careers.CAREERS) and len(set(svgs)) == len(svgs)


def test_outfit_thumbnails_follow_the_selected_career(client_for, member):
    client = client_for(member.login)
    client.post(EDITOR, {"class": "pilot"})
    member.refresh_from_db()
    pilot = services.editor_sections(services.person_config(member), member)
    client.post(EDITOR, {"class": "hse"})
    member.refresh_from_db()
    assert member.character_class == "hse"
    hse = services.editor_sections(services.person_config(member), member)

    def tiles(sections, key):
        group = next(g for s in sections for g in s["groups"] if g["key"] == key)
        return {o["id"]: o for o in group["options"]}

    assert (
        tiles(pilot, "outfit")["flight_jacket"]["rec"]
        and not tiles(hse, "outfit")["flight_jacket"]["rec"]
    )
    assert tiles(hse, "outfit")["hse_vest"]["rec"]
    assert tiles(pilot, "outfit")["blazer"]["svg"] != tiles(hse, "outfit")["blazer"]["svg"]


def test_changing_career_without_touching_the_look_dresses_the_new_career(client_for, member):
    client = client_for(member.login)
    client.post(EDITOR, {"class": "architect"})
    client.post(EDITOR, {"class": "cartographer"})  # sin JS: solo cambia la carrera
    member.refresh_from_db()
    assert member.avatar_config["outfit"] == "surveyor_jacket"
    assert member.avatar_config["prop"] == "prism_pole"
    assert (
        member.avatar_config["background"] == careers.CAREERS["cartographer"]["look"]["background"]
    )


def test_explicit_choices_win_over_the_career_look(client_for, member):
    client = client_for(member.login)
    client.post(EDITOR, {"class": "architect"})
    client.post(EDITOR, {"class": "cartographer", "outfit": "hoodie"})
    member.refresh_from_db()
    assert member.avatar_config["outfit"] == "hoodie"


def test_preview_card_shows_career_name_and_title(member_client):
    html = member_client.get(
        "/perfil/avatar/vista/", {"class": "scanner", "outfit": "jacket"}
    ).content.decode()
    assert "Especialista en Escaneo 3D" in html and "Domador de Láser" in html
    assert html.count("<svg") == 4


def test_editor_works_without_js_and_offers_the_dice_and_reduced_motion(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert (
        "?azar=1" in html and 'class="die"' in html and "<form" in html and 'method="post"' in html
    )
    css = (Path(settings.BASE_DIR) / "apps/gamification/static/gamification/editor.css").read_text(
        "utf-8"
    )
    assert "prefers-reduced-motion:no-preference" in css


def test_random_page_keeps_career_and_uses_its_palette(client_for, member):
    client = client_for(member.login)
    client.post(EDITOR, {"class": "gis"})
    for _ in range(5):
        html = client.get(EDITOR, {"azar": "1"}).content.decode()
        assert 'name="class" value="gis" checked' in html


# --- desbloqueos por nivel -------------------------------------------------------------------------------------------


def test_level_gated_pieces_show_locked_with_the_level_needed(member_client):
    html = member_client.get(EDITOR).content.decode()
    assert 'name="pin" value="theodolite_pin" disabled' in html
    assert "se desbloquea en NV 10" in html and "se desbloquea en NV 5" in html
    assert 'name="frame" value="bronze" disabled' in html and "NV 3" in html


def test_level_gated_pieces_cannot_be_saved_below_the_level(client_for, member):
    client_for(member.login).post(EDITOR, {"pin": "theodolite_pin", "frame": "bronze"})
    member.refresh_from_db()
    assert member.avatar_config["pin"] == "none" and member.avatar_config["frame"] == "common"


def test_level_gated_pieces_unlock_with_the_level():
    assert (
        avatar.clean_config({"pin": "hardhat_pin", "frame": "bronze"}, level=5)["pin"]
        == "hardhat_pin"
    )
    assert (
        avatar.clean_config({"pin": "hardhat_pin", "frame": "bronze"}, level=5)["frame"] == "bronze"
    )
    assert avatar.clean_config({"pin": "theodolite_pin"}, level=9)["pin"] == "none"
    assert avatar.clean_config({"pin": "theodolite_pin"}, level=10)["pin"] == "theodolite_pin"


def test_level_unlocks_work_end_to_end(client_for, member, monkeypatch):
    from apps.gamification import game

    monkeypatch.setattr(game, "level_info", lambda person, xp=None: {"level": 10})
    client_for(member.login).post(EDITOR, {"pin": "theodolite_pin", "frame": "bronze"})
    member.refresh_from_db()
    assert (
        member.avatar_config["pin"] == "theodolite_pin"
        and member.avatar_config["frame"] == "bronze"
    )


# --- hoja: bonos y vistas ---------------------------------------------------------------------------------------------


def test_career_bonus_adds_to_the_attributes(member):
    assert all(a["value"] == 0 for a in sheet.attributes(member, member))
    member.character_class = "cartographer"
    values = {a["code"]: a for a in sheet.attributes(member, member)}
    assert (
        values["CAP"]["value"] == 2 and values["CAP"]["bonus"] == 2 and values["ANA"]["value"] == 1
    )


def test_sheet_view_preference_and_compact_view(client_for, member):
    client = client_for(member.login)
    form = {"headline": "x", "bio": "y", "character_class": "", "sheet_view": "compact"}
    assert client.post("/perfil/editar/", form).status_code == 302
    member.refresh_from_db()
    assert member.sheet_view == "compact" and member.show_game_view is False
    html = client.get("/perfil/").content.decode()
    assert "Insignias" in html and "Vitrina de insignias" not in html and 'class="hex"' not in html
    assert "NV 1" in html and "Atributos" in html
    assert "Habilidades por vendor" in client.get("/perfil/?vista=pro").content.decode()
    client.post("/perfil/editar/", {**form, "sheet_view": "game"})
    member.refresh_from_db()
    assert member.show_game_view is True
    assert "Vitrina de insignias" in client.get("/perfil/").content.decode()
    assert "Vitrina de insignias" not in client.get("/perfil/?vista=compacta").content.decode()


# --- semillas ---------------------------------------------------------------------------------------------------------


def test_every_career_has_a_title_ladder_and_a_class_entry():
    data = json.loads((SEED / "titulos.json").read_text("utf-8"))
    assert {c["slug"] for c in data["classes"]} == set(careers.CAREERS)
    for slug, career in careers.CAREERS.items():
        entry = next(c for c in data["classes"] if c["slug"] == slug)
        assert entry["name"] == career["name"] and entry["archetype"] == career["title"]
        titles = [  # la escalera es por nivel; los títulos de una insignia con carrera van aparte
            t for t in data["titles"] if t.get("character_class") == slug and not t.get("badge")
        ]
        assert len(titles) >= 3, slug
        assert len({t["min_level"] for t in titles}) >= 3, slug
