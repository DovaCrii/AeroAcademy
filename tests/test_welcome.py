import pytest
from django.core.management import call_command

from apps.core.modules import MODULES
from apps.core.suite import SUITE_AERO

pytestmark = pytest.mark.django_db


def home(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.content.decode()


def test_welcome_greets_the_person_by_name(client_for, member):
    html = home(client_for(member.login, name="Ana Muñoz"))
    assert "Hola, Ana Muñoz" in html
    assert "Te damos la bienvenida a AeroAcademy" in html


def test_welcome_shows_the_academy_identity(member_client):
    html = home(member_client)
    assert (
        "Levantamiento" in html
        and "<b>101</b>" in html
        and "APRENDER" in html
        and "AVANZAR" in html
    )
    assert "Un equipo, un solo lugar para avanzar" in html
    for value in ("Una comunidad de profesionales", "Un solo lugar para avanzar"):
        assert value in html


def test_welcome_lists_all_modules_and_marks_availability(member_client):
    html = home(member_client)
    for module in MODULES:
        assert module["title"] in html
    assert 'href="/rutas/"' in html and 'href="/catalogo/"' in html
    assert "En construcción" not in html  # con el Bloque 11 todos los módulos están disponibles
    assert html.count("Disponible") == sum(1 for m in MODULES if m["url_name"])


def test_welcome_shows_five_disciplines(member_client):
    html = home(member_client)
    for label in ("ARQUITECTURA", "CIVIL · ESTRUCTURAL", "TOPOGRAFÍA", "MECÁNICA", "CAPTURA · RPA"):
        assert label in html


def test_welcome_without_seed_still_renders(member_client):
    html = home(member_client)
    assert "Ruta por definir con el equipo" in html
    assert "<b>0</b>" in html


def test_welcome_links_real_paths_by_discipline_after_seed(member_client):
    call_command("seed_catalog", verbosity=0)
    html = home(member_client)
    assert 'href="/rutas/forma-revit/"' in html and 'href="/rutas/bentley-learn/"' in html
    assert "Te damos la bienvenida" in html and "Puedes empezar por la" in html
    from apps.paths.models import LearningPath

    assert f"<b>{LearningPath.objects.filter(is_published=True).count()}</b>" in html  # rutas


def test_welcome_hides_unpublished_paths_from_members(member_client):
    from apps.paths.models import LearningPath

    call_command("seed_catalog", verbosity=0)
    LearningPath.objects.filter(slug="bentley-learn").update(is_published=False)
    assert "/rutas/bentley-learn/" not in home(member_client)


def test_welcome_shows_suite_aero_sponsor(member_client):
    html = home(member_client)
    assert "Auspicia" in html and "Suite Aero" in html
    assert "cuenta con el auspicio de Suite Aero" in html
    for product in SUITE_AERO:
        assert product["name"] in html


def test_suite_aero_links_open_the_apps_and_never_the_code(member_client):
    """Pedido del dueño: «quitar las rutas del código» — solo «Abrir …», ningún enlace a los repositorios."""
    html = home(member_client)
    assert "github.com" not in html and "Código ↗" not in html
    for product in SUITE_AERO:
        if product.get("app_url"):
            assert f'href="{product["app_url"]}"' in html
    assert 'rel="noopener"' in html


def test_welcome_assets_exist():
    from pathlib import Path

    from django.conf import settings

    img = Path(settings.BASE_DIR) / "apps/core/static/core/img"
    for name in ("arquitectura", "civil", "topografia", "mecanica", "equipo"):
        assert (img / f"{name}.jpg").is_file()
    assert (Path(settings.BASE_DIR) / "apps/core/static/core/welcome.css").is_file()


def test_pending_person_does_not_see_the_welcome(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    assert client_for(pending.login).get("/").status_code == 302


def test_suite_apps_show_icon_and_whether_they_are_live_or_coming(member_client):
    html = member_client.get("/").content.decode().split('id="suite"')[1]
    for product in SUITE_AERO:
        assert f"core/img/suite/{product['logo']}.svg" in html
        assert f"core/img/suite/{product['logo']}-oscuro.svg" in html
    assert html.count("En desarrollo") == sum(p["status"] == "soon" for p in SUITE_AERO) == 2
    assert html.count(">Activa<") == sum(p["status"] == "active" for p in SUITE_AERO)


def test_suite_logo_files_exist():
    from pathlib import Path

    from django.conf import settings

    suite = Path(settings.BASE_DIR) / "apps/core/static/core/img/suite"
    for product in SUITE_AERO:
        assert (suite / f"{product['logo']}.svg").is_file()
        assert (suite / f"{product['logo']}-oscuro.svg").is_file()


def test_brand_badge_in_header_and_player(member_client):
    html = home(member_client)
    assert 'class="badge101"' in html and "Levantamiento Digital" in html
    assert "<i>101</i>NV " in html


def test_module_cards_have_doodle_and_identity(member_client):
    html = home(member_client)
    for module in MODULES:
        assert f'data-m="{module["id"]}"' in html
    assert html.count('class="w-mod-ill"') == len(MODULES)


def test_active_suite_apps_link_to_their_live_page_and_soon_ones_do_not(member_client):
    html = member_client.get("/").content.decode().split('id="suite"')[1]
    for product in SUITE_AERO:
        if product["status"] == "active":
            assert product["app_url"].startswith("https://p340.tailccd107.ts.net")
            assert f'href="{product["app_url"]}"' in html
            assert f"Abrir {product['name']} ↗" in html
        else:
            assert product["app_url"] is None
    assert html.count('class="w-app-go"') == sum(p["status"] == "active" for p in SUITE_AERO)
