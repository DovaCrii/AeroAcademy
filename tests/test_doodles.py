import pytest
from django.template import Context, Template

from apps.core.templatetags.core_extras import _DOODLES, doodle

pytestmark = pytest.mark.django_db


def test_doodle_inlines_the_svg_decorative_and_with_the_class():
    html = doodle("topografia", **{"class": "dd extra"})
    assert html.startswith("<svg") and 'class="dd extra"' in html and 'aria-hidden="true"' in html
    assert "<title" not in html and 'role="img"' not in html and "<?xml" not in html
    assert "currentColor" in html


def test_doodle_aliases_the_civil_discipline_slug():
    assert doodle("civil-estructural") == doodle("civil", **{"class": "dd"})


@pytest.mark.parametrize(
    "name",
    [
        "../tokens",
        "..\\..\\x",
        "a/b",
        "TOPOGRAFIA",
        "",
        "no-such-doodle",
        "topografia.svg",
        "-x",
        None,
        3,
    ],
)
def test_doodle_rejects_names_outside_the_folder_or_missing(name):
    assert doodle(name) == ""


def test_every_doodle_file_renders():
    for path in _DOODLES.glob("*.svg"):
        assert doodle(path.stem).startswith("<svg"), path.name


def test_doodle_tag_works_in_templates_and_home_uses_it(member_client):
    out = Template(
        '{% load core_extras %}{% doodle "hero-ideas" class="dd w-hero-doodle" %}'
    ).render(Context())
    assert "w-hero-doodle" in out
    html = member_client.get("/").content.decode()
    assert "w-hero-doodle" in html and 'href="/dgac/"' in html
