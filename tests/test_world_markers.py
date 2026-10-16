"""Los marcadores («TÚ», el dron) nunca tapan etiquetas, y las estacas muestran rótulos legibles (P1-8)."""

from types import SimpleNamespace

import pytest

from apps.credentials.models import Credential
from apps.paths.models import ExternalCourse
from apps.progress import external, services


def _chapters(n, current=0, names=None):
    """Capítulos falsos (solo lo que lee `_waypoints` / `_floors`): los `current` primeros están completos."""
    out = []
    for i in range(n):
        level = SimpleNamespace(
            id=i + 1, code=f"n{i}", short=(names[i] if names else f"Nivel {i} largo del curso")
        )
        done = i < current
        out.append({"level": level, "pct": 100 if done else 0, "complete": done})
    return out


@pytest.mark.parametrize("n", range(2, 13))
def test_drone_never_overlaps_label(n):
    for current in range(n):
        flight = services._waypoints(_chapters(n, current), {}, 0)
        drones = [p for p in flight["points"] if p["here"]]
        assert len(drones) == 1
        drone = services.drone_box(drones[0])
        assert drone[0] >= 0 and drone[2] <= flight["width"]
        assert drone[1] >= 0 and drone[3] <= flight["height"]
        for p in flight["points"]:
            assert not services.boxes_overlap(drone, services.label_box(p)), (n, current, p["code"])


def test_drone_goes_opposite_to_its_label():
    flight = services._waypoints(_chapters(5, 0), {}, 0)
    first = flight["points"][0]  # etiqueta arriba → dron abajo
    assert first["above"] and first["drone_dy"] > 0
    flight = services._waypoints(_chapters(5, 1), {}, 0)
    second = flight["points"][1]  # etiqueta abajo → dron arriba
    assert not second["above"] and second["drone_dy"] < 0


def test_waypoint_labels_are_clipped_and_keep_the_full_name_for_the_title():
    flight = services._waypoints(_chapters(3, 0, ["Roles y entregables de la ruta"] * 3), {}, 0)
    p = flight["points"][0]
    assert len(p["label"]) <= services.WP_LABEL_MAX and p["label"].endswith("…")
    assert p["short"] == "Roles y entregables de la ruta"


def test_floor_labels_fit_before_the_percentage():
    long_name = "x" * 90
    floors = services._floors(_chapters(3, 0, [long_name] * 3), {}, 0)["floors"]
    assert all(len(f["label"]) <= services.FLOOR_LABEL_MAX for f in floors)
    assert 178 + services.FLOOR_LABEL_MAX * 7.5 < 508  # el nombre termina antes del porcentaje


def _course(i, title, state="none"):
    obj = SimpleNamespace(
        key=f"itw-c{i}",
        resource=SimpleNamespace(title=title),
        reward=ExternalCourse.Reward.TROPHY,
    )
    return {"obj": obj, "state": state}


TITLES = [
    "Introduction to iTwin Platform",
    "Reality Modeling Fundamentals",
    "OpenRoads Designer Corridor Modeling",
    "Bentley Accredited Professional: iModel",
]


@pytest.mark.parametrize("n", [1, 2, 4, 8, 12])
def test_civil_marker_clear_of_stake(n):
    verified = Credential.Status.VERIFIED
    for done in range(n + 1):
        courses = [
            _course(i, TITLES[i % len(TITLES)], verified if i < done else "none") for i in range(n)
        ]
        j = external._journey(courses, [])
        mx, my = float(j["marker_x"]), float(j["marker_y"])
        circle = (mx - 11, my - 11, mx + 11, my + 11)
        chars_w = external.STAKE_CHAR_W
        for s in j["stakes"]:
            x, y = float(s["x"]), float(s["y"])
            pole_and_flag = (x - 2, y - 8, x + 16, y + 24)
            label_w = len(s["label"]) * chars_w
            label = (x - label_w / 2, y - 24, x + label_w / 2, y - 14)
            assert not services.boxes_overlap(circle, pole_and_flag), (n, done, s["key"])
            assert not services.boxes_overlap(circle, label), (n, done, s["key"])


@pytest.mark.parametrize("title", TITLES)
def test_stake_labels_are_human(title):
    label = external.stake_label(title, 20)
    assert label and "itw-" not in label and "-c" not in label
    assert len(label) <= 20
    # Dos palabras con contenido; sin «Introduction to».
    assert not label.lower().startswith(("introduction", "to "))


def test_stake_labels_never_show_the_raw_key():
    j = external._journey([_course(0, "Intro to iTwin"), _course(1, "Reality Modeling")], [])
    assert [s["label"] for s in j["stakes"]] == ["iTwin", "Reality Modeling"]
    assert all(s["label"] != s["key"] for s in j["stakes"])
