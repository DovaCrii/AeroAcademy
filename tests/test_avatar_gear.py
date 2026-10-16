"""Equipo HD por disciplina (HD-4 y HD-5): ids nuevos, carriles, tamaños mínimos y cableado en las carreras."""

import pytest

from apps.gamification import avatar
from apps.gamification.avatar import careers, engine, hd
from apps.gamification.avatar.hd import compose as hd_compose
from apps.gamification.avatar.hd import render as hd_render
from apps.gamification.avatar.parts import props
from apps.gamification.avatar.validation import validate_category, validate_hd

pytestmark = pytest.mark.django_db

NEW_PROPS = [
    "total_station",
    "level_staff",
    "laptop_bim",
    "traffic_cone",
    "pipe_spool",
    "valve_wheel",
    "laptop_ai",
]
OLD_PROPS = [
    "none", "tablet", "prism_pole", "gnss_rover", "drone_controller", "scale_ruler", "mug",
    "plans_roll", "wrench", "clipboard", "calculator", "camera", "laser_scanner",
]  # fmt: skip


def pieces(prop):
    art = hd.HD["prop"][prop]
    return art if isinstance(art, list) else [art]


def bbox(sprite):
    x, y = sprite["at"]
    return x, y, x + max(len(r) for r in sprite["rows"]) - 1, y + len(sprite["rows"]) - 1


def test_new_props_are_appended_labeled_and_have_a_32_version():
    ids = list(props.PROPS)
    assert ids[: len(OLD_PROPS)] == OLD_PROPS  # los índices guardados no se mueven
    assert ids[len(OLD_PROPS) :] == NEW_PROPS
    for prop in NEW_PROPS:
        assert props.LABELS_PROPS[prop] and props.PROPS[prop], prop
    assert validate_category("props") == []  # la versión de 32 cumple el contrato


def test_every_tool_has_an_hd_version_with_stable_ids():
    assert set(hd.HD["prop"]) == set(props.PROPS) - {"none"}
    assert validate_hd(["prop"]) == []


def test_new_props_are_reachable_in_the_editor_and_by_careers(member_client):
    html = member_client.get("/perfil/avatar/").content.decode()
    for prop in NEW_PROPS:
        assert f'name="prop" value="{prop}"' in html, prop
    offered = {p for data in careers.CAREERS.values() for p in data["props"]}
    assert set(NEW_PROPS) <= offered
    for data in careers.CAREERS.values():
        assert set(data["props"]) <= set(props.PROPS)
        assert data["look"]["prop"] in props.PROPS


def test_survey_capture_civil_plant_bim_and_ai_get_their_gear():
    assert {"total_station", "level_staff"} <= set(careers.CAREERS["cartographer"]["props"])
    assert "traffic_cone" in careers.CAREERS["engineer"]["props"]
    assert {"pipe_spool", "valve_wheel"} <= set(careers.CAREERS["artificer"]["props"])
    assert "laptop_bim" in careers.CAREERS["architect"]["props"]
    assert "laptop_ai" in careers.CAREERS["bim_modeler"]["props"]


@pytest.mark.parametrize("prop", sorted(set(props.PROPS) - {"none"}))
def test_gear_stays_in_its_lane_and_off_the_face(prop):
    """Carril derecho (x ≥ 54), izquierdo (x ≤ 23), aire (y ≤ 11) o suelo; nunca sobre la ventana de la cara."""
    for sprite in pieces(prop):
        assert sprite["space"] == "stage"
        ax, ay = sprite["at"]
        for j, row in enumerate(sprite["rows"]):
            for i, ch in enumerate(row):
                if ch == ".":
                    continue
                x, y = ax + i, ay + j
                assert not (x in hd_compose.FACE_X and y in hd_compose.FACE_Y), (prop, x, y)
                assert x >= 54 or x <= 23 or y <= 11, (prop, x, y)


def test_minimum_legible_sizes():
    def size(prop, index=0):
        x0, y0, x1, y1 = bbox(pieces(prop)[index])
        return x1 - x0 + 1, y1 - y0 + 1

    for hand_tool in (
        "tablet",
        "laptop_bim",
        "laptop_ai",
        "clipboard",
        "camera",
        "mug",
        "calculator",
    ):
        w, h = size(hand_tool)
        assert max(w, h) >= 12 and min(w, h) >= 9, (hand_tool, w, h)
    for tall in ("prism_pole", "gnss_rover", "level_staff"):
        w, h = size(tall)
        assert w >= 4 and h >= 60, (tall, w, h)
    assert size("prism_pole")[0] >= 10  # el prisma
    assert size("drone_controller", 1) == (22, 9)  # el dron
    w, h = size("total_station")
    assert w >= 14 and h >= 24
    assert size("traffic_cone")[1] >= 12 and size("laptop_ai")[0] >= 16


def test_drone_flies_in_the_air_lane_above_the_controller():
    control, drone = pieces("drone_controller")
    assert bbox(drone)[3] <= 11 < bbox(control)[1]


@pytest.mark.parametrize("prop", sorted(set(props.PROPS) - {"none"}))
def test_each_tool_renders_in_hd_within_budget(prop):
    hd_render._stage_body.cache_clear()
    svg = avatar.render_svg({"prop": prop, "class": "cartographer"}, view="stage")
    assert 'viewBox="0 0 80 80"' in svg and len(svg) < 16_000


def test_tools_look_different_from_each_other_in_hd():
    svgs = {avatar.render_svg({"prop": p}, view="stage") for p in engine.CHOICES["prop"]}
    assert len(svgs) == len(engine.CHOICES["prop"])


def test_gear_does_not_change_the_32_silhouette_of_old_tools():
    """Las herramientas de siempre siguen igual en las vistas de 32."""
    for prop in OLD_PROPS:
        assert avatar.render_svg({"prop": prop}).startswith("<svg")
