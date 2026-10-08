import json
from pathlib import Path

from django.conf import settings

from apps.gamification import avatar as av

SEED = Path(settings.BASE_DIR) / "seed"


def load(name):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def test_titles_are_well_formed():
    data = load("titulos.json")
    slugs = [t["slug"] for t in data["titles"]]
    assert len(slugs) == len(set(slugs)), "slugs de títulos repetidos"
    classes = {c["slug"] for c in data["classes"]}
    badges = {b["slug"] for b in load("insignias.json")["badges"]}
    for t in data["titles"]:
        assert t.get("min_level") or t.get("badge"), t
        assert isinstance(t.get("min_level", 1), int) and t.get("min_level", 1) >= 1
        assert not t.get("character_class") or t["character_class"] in classes
        assert not t.get("badge") or t["badge"] in badges


def test_every_class_has_a_title_ladder():
    titles = load("titulos.json")["titles"]
    for cls in ("architect", "engineer", "cartographer", "artificer", "pilot"):
        assert sum(1 for t in titles if t.get("character_class") == cls) >= 2, cls


def test_avatar_classes_match_the_title_classes():
    assert {c["slug"] for c in load("titulos.json")["classes"]} == set(av.CLASSES)


def test_badges_are_well_formed():
    badges = load("insignias.json")["badges"]
    slugs = [b["slug"] for b in badges]
    assert len(slugs) == len(set(slugs))
    assert {b["rarity"] for b in badges} <= {"common", "rare", "epic", "legendary"}
