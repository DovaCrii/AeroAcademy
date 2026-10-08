import pytest

from apps.gamification.avatar import audit, engine


@pytest.mark.parametrize("check", audit.CHECKS, ids=lambda c: c.__name__)
def test_pieces_fit_together(check):
    assert check() == []


def test_audit_reports_nothing_overall():
    assert audit.run_all() == []


# --- reglas de encaje del motor ---------------------------------------------------------------------------------


def _eye_cells(eyes):
    art = engine.EYES[eyes]
    return {(x, y): ch for y, line in art.items() for x, ch in enumerate(line) if ch in "EeWw"}


def test_transparent_glasses_are_drawn_under_the_eyes():
    cfg = engine.clean_config({"eyes": "iris", "glasses": "round"})
    grid = engine.compose(cfg)
    assert all(grid[y][x] == ch for (x, y), ch in _eye_cells("iris").items())


def test_opaque_glasses_are_drawn_over_the_eyes():
    base = engine.compose(engine.clean_config({"eyes": "dot"}))
    dark = engine.compose(engine.clean_config({"eyes": "dot", "glasses": "sunglasses"}))
    assert base != dark
    assert any(dark[y][x] == "F" for y in range(9, 13) for x in range(11, 21))


def test_hair_never_pokes_above_a_hat():
    cfg = engine.clean_config({"hair": "afro", "headwear": "beanie", "hair_color": 0})
    grid = engine.compose(cfg)
    top = engine._hat_top(engine.HEADWEAR["beanie"])
    assert not any(ch in "Hhj" for y in range(top) for ch in grid[y])


def test_without_a_hat_the_hair_is_not_clipped():
    grid = engine.compose(engine.clean_config({"hair": "afro", "headwear": "none"}))
    assert any(ch == "H" for ch in grid[1]) or any(ch == "H" for ch in grid[0])


def test_engine_clips_anything_that_falls_on_the_face(monkeypatch):
    bad = {
        "back": {},
        "front": {12: "." * 14 + "TT" + "." * 16},
    }  # un gorro defectuoso sobre la nariz
    monkeypatch.setitem(engine.HEADWEAR, "bad", bad)
    grid = engine.compose(engine.clean_config({"headwear": "bad"}))
    assert grid[12][14] != "T" and grid[12][15] != "T"


def test_hat_over_every_hair_keeps_the_face_visible():
    for hat in engine.HEADWEAR:
        for hair in engine.HAIR:
            grid = engine.compose(
                engine.clean_config({"hair": hair, "headwear": hat, "eyes": "iris"})
            )
            assert grid[12][12] in "WeE", (hat, hair)  # fila de abajo del ojo izquierdo


def test_ponytail_back_hair_is_also_clipped_by_a_hat():
    cfg = engine.clean_config({"hair": "ponytail", "headwear": "hardhat", "hair_color": 0})
    grid = engine.compose(cfg)
    top = engine._hat_top(engine.HEADWEAR["hardhat"])
    assert not any(ch in "Hhj" for y in range(top) for ch in grid[y])
