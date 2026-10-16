import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_catalog_external_links_are_marked(member_client):
    """P0-1: el título que sale del sitio lleva ↗ y dice de qué sitio es."""
    call_command("seed_catalog", verbosity=0)
    html = member_client.get("/catalogo/").content.decode()
    assert 'class="ext-ico"' in html
    assert "(abre el sitio de " in html
    assert 'target="_blank" rel="noopener" aria-label=' in html
