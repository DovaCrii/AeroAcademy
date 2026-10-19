"""`manage.py revisar_enlaces`: sin red (el comprobador externo se reemplaza por uno falso)."""

import csv
import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.catalog.models import Platform, Resource
from apps.core import linkcheck

pytestmark = pytest.mark.django_db


def test_classify_separates_404_from_blocks_and_timeouts():
    assert linkcheck.classify(404) == "roto"
    assert linkcheck.classify(410) == "roto"
    assert linkcheck.classify(403) == "bloqueado"
    assert linkcheck.classify(429) == "bloqueado"
    assert linkcheck.classify(500) == "error_servidor"
    assert linkcheck.classify("TimeoutError") == "sin_respuesta"
    assert linkcheck.classify(200) == "ok"


def test_bentley_learn_items_are_checked_through_their_api(monkeypatch):
    seen = []

    class Reply:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, *args):
            return self.body

    def fake_urlopen(request, timeout=0):
        seen.append(request.full_url)
        if "/courses/1?" in request.full_url or "/lp/2?" in request.full_url:
            return Reply(b'{"data": {"name": "Curso"}}')
        raise linkcheck.urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(linkcheck.urllib.request, "urlopen", fake_urlopen)
    base = "https://learning.bentley.com/learn/"
    assert linkcheck.check_url(base + "courses/1/curso") == 200
    assert linkcheck.check_url(base + "course/1/curso") == 200
    assert linkcheck.check_url(base + "learning-plans/2/plan") == 200
    assert linkcheck.check_url(base + "courses/99999999/no-existe") == 404
    assert linkcheck.check_bentley_item(base + "learn") is None
    assert all("/learn/v1/" in url for url in seen)


def test_seed_urls_finds_urls_in_json(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps({"x": [{"url": "https://ejemplo.test/a."}]}), encoding="utf-8"
    )
    assert linkcheck.seed_urls(tmp_path) == {"https://ejemplo.test/a": "a.json"}


def test_external_check_writes_csv_and_separates_classes(tmp_path, monkeypatch, admin_person):
    platform = Platform.objects.create(name="Plataforma de prueba", slug="p", kind="vendor")
    Resource.objects.create(platform=platform, title="Roto", url="https://ejemplo.test/roto")
    Resource.objects.create(
        platform=platform, title="Bloqueado", url="https://ejemplo.test/bloqueado"
    )
    codes = {"https://ejemplo.test/roto": 404, "https://ejemplo.test/bloqueado": 403}
    monkeypatch.setattr(linkcheck, "check_url", lambda url, timeout=15: codes.get(url, 200))
    out = StringIO()
    call_command("revisar_enlaces", "--solo-externos", "--salida", str(tmp_path), stdout=out)
    text = out.getvalue()
    assert "404 real: https://ejemplo.test/roto" in text
    assert "bloqueado" in text
    rows = list(csv.reader(next(tmp_path.glob("enlaces_externos_*.csv")).open(encoding="utf-8")))
    by_url = {r[0]: r for r in rows[1:]}
    assert by_url["https://ejemplo.test/roto"][3] == "roto"
    assert by_url["https://ejemplo.test/bloqueado"][3] == "bloqueado"
    assert all(r[1] for r in rows[1:])  # cada fila dice de dónde sale la URL


def test_internal_crawl_runs_and_reports_clean_site(tmp_path, admin_person, settings):
    settings.MEDIA_ROOT = tmp_path
    out = StringIO()
    call_command("revisar_enlaces", "--limite", "30", "--salida", str(tmp_path), stdout=out)
    assert "Internos rotos: 0" in out.getvalue()
    assert next(tmp_path.glob("enlaces_internos_*.csv")).exists()


def test_internal_crawl_needs_an_admin(tmp_path):
    with pytest.raises(CommandError):
        call_command("revisar_enlaces", "--salida", str(tmp_path))
