"""Cabecera: cinco principales + «Más» + hamburguesa sin JS, sin cinta duplicada en la portada y tokens de elevación."""

import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings

from apps.core.navigation import MAIN_NAV, MORE_NAV

MAIN_HREFS = ["/", "/rutas/", "/catalogo/", "/foro/", "/equipo/"]
MORE_LABELS = ["Certificados", "Documentos", "Conocimiento", "Gremio", "DGAC", "Ayuda"]
CORE_CSS = Path(settings.BASE_DIR) / "apps/core/static/core"


class _Nav(HTMLParser):
    """Recoge, por <div> de la cabecera, los enlaces del navegador `nav.nav`."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.groups: dict[str, list[tuple[str, str]]] = {}
        self._href = None
        self._text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag == "nav" and "nav" in cls.split():
            self.stack.append("nav")
        elif self.stack and tag in ("div", "details"):
            key = next(
                (k for k in ("nav-main", "nav-more", "nav-burger") if k in cls.split()), None
            )
            self.stack.append(key or "x")
            if key:
                self.groups.setdefault(key, [])
        elif self.stack and tag == "a":
            self._href, self._text = a.get("href"), ""

    def handle_data(self, data):
        if self._href is not None:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None and self.stack:
            owner = next(
                (s for s in reversed(self.stack) if s in ("nav-main", "nav-more", "nav-burger")),
                None,
            )
            if owner:
                self.groups[owner].append((self._text.strip(), self._href))
            self._href = None
        elif tag in ("nav", "div", "details") and self.stack:
            self.stack.pop()


def nav_groups(html):
    p = _Nav()
    p.feed(html)
    return p.groups


def test_header_has_five_primary_links_and_more(member_client):
    g = nav_groups(member_client.get("/rutas/").content.decode())
    assert [h for _, h in g["nav-main"]] == MAIN_HREFS
    assert [t for t, _ in g["nav-main"]] == ["Inicio", "Rutas", "Catálogo", "Foro", "Equipo"]
    html = member_client.get("/rutas/").content.decode()
    assert '<details class="nav-more">' in html


def test_more_menu_contains_secondary_sections(member_client, client_for, lead):
    g = nav_groups(member_client.get("/").content.decode())
    assert [t for t, _ in g["nav-more"]] == MORE_LABELS
    assert len(g["nav-more"]) <= 7
    assert "/certificados/" not in [h for _, h in g["nav-main"]]
    assert "Moderación" not in [t for t, _ in g["nav-more"]]
    lead_nav = nav_groups(client_for(lead.login).get("/").content.decode())
    assert [t for t, _ in lead_nav["nav-more"]] == [*MORE_LABELS, "Moderación"]


def test_burger_menu_works_without_js_and_has_every_section(member_client):
    html = member_client.get("/").content.decode()
    g = nav_groups(html)
    assert '<details class="nav-burger"><summary>Menú</summary>' in html
    burger = [h for _, h in g["nav-burger"]]
    assert burger == [*MAIN_HREFS, *[h for _, h in g["nav-more"]]]


def test_current_section_is_marked_and_more_is_highlighted(member_client):
    html = member_client.get("/rutas/").content.decode()
    assert re.search(r'<a href="/rutas/" aria-current="page">Rutas</a>', html)
    docs = member_client.get("/documentos/").content.decode()
    assert '<summary class="on">Más</summary>' in docs


def test_main_nav_is_defined_in_one_place():
    labels = [i.label for i in MAIN_NAV]
    assert labels == ["Inicio", "Rutas", "Catálogo", "Foro", "Equipo"]
    assert "Certificados" in [i.label for i in MORE_NAV]


def test_user_menu_has_my_certificates_and_theme(member_client):
    html = member_client.get("/").content.decode()
    menu = html[
        html.index('<div class="um-pop">') : html.index(
            "</details>", html.index('<div class="um-pop">')
        )
    ]
    assert 'href="/certificados/">Mis certificados</a>' in menu
    assert 'id="themeBtn"' in menu
    assert html.count('id="themeBtn"') == 1


def test_home_has_no_duplicate_quicknav(member_client):
    html = member_client.get("/").content.decode()
    assert "w-strip" not in html and "Accesos rápidos" not in html
    header_hrefs = {h for g in nav_groups(html).values() for _, h in g}
    # los <nav> de la portada solo traen anclas de la página (ningún href de la cabecera)
    for nav in re.findall(r"<nav\b[^>]*>.*?</nav>", html, flags=re.S):
        if 'class="nav"' in nav or "w-circles" in nav:
            continue
        hrefs = set(re.findall(r'href="([^"]*)"', nav))
        assert not (hrefs & header_hrefs), hrefs & header_hrefs
    jump = re.search(
        r'<nav class="w-jump" aria-label="En esta página">(.*?)</nav>', html, flags=re.S
    ).group(1)
    assert all(h.startswith("#") for h in re.findall(r'href="([^"]*)"', jump))
    assert html.count('class="w-jump"') == 1


def test_header_css_has_no_horizontal_scroll_and_burger():
    css = (CORE_CSS / "base.css").read_text(encoding="utf-8")
    nav_main = re.search(r"\.nav-main\{[^}]*\}", css).group(0)
    assert "overflow-x" not in nav_main and "mask" not in nav_main
    assert "max-width:1023px" in css and ".nav-burger{display:block}" in css


def test_tokens_define_elevation_and_discipline_accents():
    css = (CORE_CSS / "tokens.css").read_text(encoding="utf-8")
    assert "--surface-0:" in css
    for token in ("--elev-1", "--elev-2", "--elev-3", "--surface-1", "--surface-2"):
        assert css.count(f"{token}:") >= 3, token  # claro + las dos formas del oscuro
    for slug in ("arq", "civ", "top", "mec", "cap", "iad", "tra"):
        assert f"--disc-{slug}:" in css
    comp = (CORE_CSS / "components.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion:reduce" in comp and "var(--elev-2)" in comp


def _luminance(hex_color):
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def test_dark_card_surface_separates_from_background():
    css = (CORE_CSS / "tokens.css").read_text(encoding="utf-8")
    dark = css[css.index(':root[data-theme="dark"]') :]
    bg = re.search(r"--bg:(#[0-9A-Fa-f]{6})", dark).group(1)
    card = re.search(r"--surface-1:(#[0-9A-Fa-f]{6})", dark).group(1)
    hi, lo = sorted((_luminance(card), _luminance(bg)), reverse=True)
    assert (hi + 0.05) / (lo + 0.05) >= 1.25
