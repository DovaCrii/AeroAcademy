"""Centro de administración (D42), P1-1: salud, respaldo, versión, puerta pública y cursos privados del servidor."""

import os
import threading
import time
from collections import namedtuple
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core import admin_center
from tests.conftest import own_queries, tailscale_client

pytestmark = pytest.mark.django_db
URL = "/administracion/"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated(settings, tmp_path, monkeypatch):
    """Carpetas de prueba y sin sonda de red por defecto (cada prueba que la necesita la arma)."""
    cache.clear()
    settings.BACKUP_DIR = tmp_path / "respaldos"
    settings.VERSION_FILE = tmp_path / "version"
    settings.PREV_INFO_FILE = tmp_path / "prev.info"
    settings.PRIVATE_COURSES_DIR = tmp_path / "cursos"
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(admin_center, "public_door_up", lambda: False)
    yield
    cache.clear()


def page(admin_person):
    response = tailscale_client(admin_person.login).get(URL)
    assert response.status_code == 200
    return response.content.decode().split("<main")[1]


def make_backups(folder: Path, *, hours_old=2.0, days=3):
    folder.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for i in range(days):
        stamp = (timezone.localdate() - timedelta(days=i)).isoformat()
        for name, size in ((f"db-{stamp}.sqlite3", 2048), (f"media-{stamp}.tar.gz", 4096)):
            path = folder / name
            path.write_bytes(b"x" * size)
            moment = now - hours_old * 3600 - i * 86400
            os.utime(path, (moment, moment))
    pre = folder / "pre-actualizar-20261018T153000Z.sqlite3"
    pre.write_bytes(b"x" * 100)
    moment = now - 2 * 86400
    os.utime(pre, (moment, moment))


# --- respaldos ---------------------------------------------------------------------------------------------------


def test_latest_backups_picks_the_newest_and_counts_the_kept(settings):
    make_backups(settings.BACKUP_DIR, days=4)
    data = admin_center.latest_backups()
    today = timezone.localdate().isoformat()
    assert data["found"] and data["db"]["name"] == f"db-{today}.sqlite3"
    assert data["media"]["name"] == f"media-{today}.tar.gz"
    assert data["kept"] == 4 and data["pre"]["name"].startswith("pre-actualizar-")
    assert data["db"]["size"] == "2 KB" and data["media"]["size"] == "4 KB"


def test_the_backup_row_shows_name_date_size_and_how_many(admin_person, settings):
    make_backups(settings.BACKUP_DIR, days=3)
    html = page(admin_person)
    today = timezone.localdate().isoformat()
    assert f"db-{today}.sqlite3" in html and f"media-{today}.tar.gz" in html
    assert "hoy " in html and "2 KB" in html
    assert "3 respaldos diarios guardados" in html and "Último previo a actualizar" in html


def test_no_backup_folder_says_so(admin_person):
    html = page(admin_person)
    assert "No hay respaldos a la vista." in html


def test_an_old_backup_is_a_warning(admin_person, settings):
    make_backups(settings.BACKUP_DIR, hours_old=40, days=1)
    html = page(admin_person)
    assert "hace más de un día y medio" in html
    cards = {c.key: c for c in admin_center.situation("admin", server=admin_center.server_status())}
    assert cards["server"].warn


def test_a_fresh_backup_is_not_a_warning(admin_person, settings):
    make_backups(settings.BACKUP_DIR, hours_old=1, days=1)
    status = admin_center.server_status()
    backup = next(c for g in status["groups"] if g["label"] == "Respaldo" for c in g["checks"])
    assert backup.state == "ok"


def test_other_files_in_the_folder_are_ignored(admin_person, settings):
    make_backups(settings.BACKUP_DIR, days=1)
    (settings.BACKUP_DIR / "secretos.txt").write_text("nvapi-no-debe-salir")
    (settings.BACKUP_DIR / "db-mal.sqlite3").write_bytes(b"x")
    (settings.BACKUP_DIR / "subcarpeta").mkdir()
    html = page(admin_person)
    assert "secretos.txt" not in html and "db-mal" not in html and "nvapi" not in html


def test_only_basenames_reach_the_page(admin_person, settings, tmp_path):
    make_backups(settings.BACKUP_DIR, days=1)
    version = settings.VERSION_FILE
    version.write_text("commit=a1b2c3d4\ndeployed_at=2026-10-18T10:00:00Z\n")
    (settings.PRIVATE_COURSES_DIR / "una-ruta").mkdir(parents=True)
    (settings.PRIVATE_COURSES_DIR / "una-ruta" / "ruta.json").write_text("{}")
    html = page(admin_person)
    for needle in (
        str(tmp_path),
        tmp_path.name,
        "pytest-of",
        str(settings.BACKUP_DIR),
        str(settings.MEDIA_ROOT),
        str(settings.PRIVATE_COURSES_DIR),
        str(settings.VERSION_FILE),
        str(settings.DATABASES["default"]["NAME"]),
        "/var/",
        "/opt/",
        "private",
        ".sqlite3\\",
    ):
        assert needle not in html, needle


# --- comprobaciones que fallan -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func",
    [
        "_database_checks",
        "_storage_checks",
        "_cache_checks",
        "_nala_checks",
        "_backup_checks",
        "_version_checks",
        "_courses_checks",
    ],
)
def test_a_failing_check_says_it_could_not_check_and_never_breaks_the_page(
    func, admin_person, monkeypatch
):
    def boom():
        raise RuntimeError("/var/secreto/ruta falló con nvapi-123")

    monkeypatch.setattr(admin_center, func, boom)
    html = page(admin_person)  # 200, no 500
    assert "No se pudo comprobar." in html
    assert "/var/secreto" not in html and "nvapi-123" not in html  # ni el mensaje del error


def test_a_dead_disk_read_does_not_break_the_center(admin_person, monkeypatch):
    monkeypatch.setattr(
        admin_center.shutil, "disk_usage", lambda p: (_ for _ in ()).throw(OSError("x"))
    )
    assert "No se pudo comprobar." in page(admin_person)


# --- salud ---------------------------------------------------------------------------------------------------


def test_health_rows_in_a_normal_server(admin_person, settings, tmp_path):
    (tmp_path / "media").mkdir()
    html = page(admin_person)
    assert "Base de datos:</b> Responde" in html
    assert "Archivos privados:</b> Se puede escribir · disco con" in html
    assert "memoria que protege la entrada funciona" in html
    assert "Nala:</b> Dormida" in html


def test_nala_configured_is_shown_without_the_key(admin_person, settings):
    settings.BOT_ENABLED = True
    settings.NIM_API_KEY = "nv" + "api-prueba-que-no-debe-salir-9f8e7d"
    html = page(admin_person)
    assert "Nala:</b> Configurada." in html
    assert "nvapi" not in html and "9f8e7d" not in html


def test_unwritable_media_and_low_disk_are_warnings(admin_person, settings, monkeypatch):
    html = page(admin_person)  # la carpeta de archivos no existe en esta prueba
    assert "No se puede escribir en su carpeta." in html
    settings.MEDIA_ROOT.mkdir()
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(admin_center.shutil, "disk_usage", lambda p: usage(1000, 960, 40))
    assert "el disco tiene solo 4 % libre" in page(admin_person)


def test_a_cache_that_forgets_is_a_warning(admin_person, monkeypatch):
    monkeypatch.setattr(admin_center.cache, "get", lambda *a, **k: None)
    assert "no guarda datos" in page(admin_person)


def test_every_row_has_a_symbol_and_words_never_only_color(admin_person):
    html = page(admin_person)
    assert 'class="ac-st ok" aria-hidden="true">✓' in html
    assert "En orden: " in html and "Sin dato: " in html


# --- versión -----------------------------------------------------------------------------------------------------


def test_version_from_the_version_file(admin_person, settings):
    settings.VERSION_FILE.write_text(
        "commit=A1B2C3D4E5\ntag=v1.2\ndeployed_at=2026-10-18T10:00:00Z\n"
    )
    version = admin_center.deployed_version()
    assert version["commit"] == "a1b2c3d4" and version["tag"] == "v1.2"
    html = page(admin_person)
    assert "a1b2c3d4 (v1.2) · instalada el 18/10/2026" in html


def test_version_falls_back_to_the_last_update_info(admin_person, settings):
    settings.PREV_INFO_FILE.write_text(
        "commit_before=1111111\ncommit_after=deadbeef99\ntaken_at=2026-10-17T08:00:00Z\n"
    )
    assert admin_center.deployed_version()["commit"] == "deadbeef"
    assert "deadbeef" in page(admin_person)
    settings.VERSION_FILE.write_text("commit=cafe1234\ndeployed_at=2026-10-19T08:00:00Z\n")
    assert (
        admin_center.deployed_version()["commit"] == "cafe1234"
    )  # el archivo del instalador manda


def test_version_without_any_file_says_no_data(admin_person):
    assert admin_center.deployed_version() is None
    assert "Sin dato: la app no puede saber qué versión está instalada." in page(admin_person)


def test_version_files_with_junk_are_ignored_or_escaped(admin_person, settings):
    settings.VERSION_FILE.write_text("commit=<script>alert(1)</script>\n")
    assert admin_center.deployed_version() is None
    settings.VERSION_FILE.write_text("commit=abcdef12\ntag=<b>x</b>\ndeployed_at=ayer\n")
    version = admin_center.deployed_version()
    assert version["tag"] == "" and version["at"] is None
    assert "<script>" not in page(admin_person)
    settings.VERSION_FILE.write_bytes(b"x" * 5000)  # demasiado grande: se ignora
    assert admin_center.deployed_version() is None


# --- puerta pública ------------------------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    hosts: list = []

    def do_GET(self):  # noqa: N802
        type(self).hosts.append((self.path, self.headers.get("Host")))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):
        pass


def test_the_public_door_probe_hits_healthz_with_the_site_host_and_is_cached(settings, monkeypatch):
    monkeypatch.undo()  # esta prueba usa la sonda real
    _Handler.hosts = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings.PUBLIC_DOOR_PORT = server.server_address[1]
        settings.ALLOWED_HOSTS = ["aeroacademy.ejemplo.ts.net"]
        cache.clear()
        assert admin_center.public_door_up() is True
        assert admin_center.public_door_up() is True  # la segunda sale de la caché
        assert _Handler.hosts == [("/healthz", "aeroacademy.ejemplo.ts.net")]
    finally:
        server.shutdown()
        server.server_close()
    cache.clear()
    assert admin_center.public_door_up() is False  # ya nadie escucha ahí
    assert cache.get(admin_center.PUBLIC_PROBE_KEY) == "down"  # y también se acuerda de eso


def test_the_probe_never_waits_more_than_half_a_second(monkeypatch):
    monkeypatch.undo()  # la sonda real, con la red simulada
    seen = {}

    def slow(request, timeout=None):
        seen["timeout"] = timeout
        raise TimeoutError

    monkeypatch.setattr(admin_center.urllib.request, "urlopen", slow)
    cache.clear()
    assert admin_center.public_door_up() is False
    assert seen["timeout"] == 0.5


def test_the_door_rows_are_honest_about_what_the_app_can_know(admin_person, monkeypatch):
    html = page(admin_person)
    assert "El servicio no responde." in html and "El Funnel se revisa en la VM." in html
    monkeypatch.setattr(admin_center, "public_door_up", lambda: True)
    html = page(admin_person)
    assert "El servicio está en marcha." in html and "se revisa en la VM" in html
    # apagada no es un aviso: puede estar apagada a propósito
    monkeypatch.setattr(admin_center, "public_door_up", lambda: False)
    door = next(
        c
        for g in admin_center.server_status()["groups"]
        if g["label"] == "Puerta pública"
        for c in g["checks"]
    )
    assert door.state == "none"


# --- cursos privados -----------------------------------------------------------------------------------------


def test_private_courses_counts_only(admin_person, settings):
    assert "Carpeta no instalada (es opcional)." in page(admin_person)
    call_command("seed_catalog", verbosity=0)
    root = settings.PRIVATE_COURSES_DIR
    for slug in ("forma-revit", "ruta-que-no-esta"):
        (root / slug).mkdir(parents=True)
        (root / slug / "ruta.json").write_text("{}")
    (root / "solo-fotos").mkdir()
    assert admin_center.private_courses() == {"installed": True, "folders": 2, "loaded": 1}
    html = page(admin_person)
    assert "1 de 2 cargados." in html and "cargar_cursos_privados" in html
    assert "ruta-que-no-esta" not in html and "forma-revit</" not in html


# --- tarjeta del servidor y consultas -------------------------------------------------------------------------


def test_the_server_card_adds_up_the_warnings(admin_person, monkeypatch):
    fake = {"groups": [], "warnings": 2}
    cards = {c.key: c for c in admin_center.situation("admin", server=fake)}
    assert cards["server"].value == "2" and cards["server"].warn
    assert cards["server"].url == "/administracion/#servidor"
    ok = {c.key: c for c in admin_center.situation("admin", server={"groups": [], "warnings": 0})}
    assert ok["server"].value == "✓" and not ok["server"].warn
    html = page(admin_person)
    assert (
        "avisos del servidor" in html or "aviso del servidor" in html
    )  # la prueba corre sin respaldos


def test_the_lead_never_sees_the_server(lead):
    html = tailscale_client(lead.login).get(URL).content.decode()
    assert 'id="servidor"' not in html and "Respaldo" not in html and "Puerta pública" not in html


def test_the_center_with_the_server_block_stays_bounded(admin_person, member, settings, tmp_path):
    (tmp_path / "media").mkdir()
    make_backups(settings.BACKUP_DIR, days=5)
    client = tailscale_client(admin_person.login)
    client.get(URL)
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(URL).status_code == 200
    own = own_queries(ctx.captured_queries)
    assert len(own) <= 15


# --- instalador ----------------------------------------------------------------------------------------------


def test_the_installer_writes_the_version_file_and_tolerates_failures():
    install = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "\r" not in install
    code = [line for line in install.splitlines() if not line.strip().startswith("#")]
    text = "\n".join(code)
    assert ".deployed-version" in text
    start = text.index("==> Versión instalada")
    block = text[start : text.index("==> Configuración en")]
    assert "rev-parse --short" in block and "deployed_at=" in block and "commit=" in block
    assert block.count("|| true") >= 2  # ni git ni la escritura pueden detener el instalador
    for secret in ("SECRET_KEY", "NIM_API_KEY", "ENV_FILE", "/etc/centro", "TS_AUTHKEY"):
        assert secret not in block
    # va después de copiar el código y antes de dar el dueño de /opt/aeroacademy al usuario del servicio
    assert (
        text.index('"$SRC"/ "$APP"/')
        < start
        < text.index('chown -R "$USER_NAME:$USER_NAME" "$APP"')
    )


def test_the_default_version_file_matches_what_the_installer_writes():
    from config.settings import base

    assert base.VERSION_FILE.name == ".deployed-version"
    assert base.VERSION_FILE.parent == base.BASE_DIR
    assert str(base.PREV_INFO_FILE).endswith(".prev.info")
    assert base.PUBLIC_DOOR_PORT == 8011 and str(base.BACKUP_DIR).endswith("centro")
    assert "/administracion/" in base.PUBLIC_BLOCKED_PREFIXES
