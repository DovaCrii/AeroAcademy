"""Centro de administración (D42), P1-2: registro de ejecuciones de tareas y su estado en el Centro."""

import io
import os
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core import admin_center, taskruns
from apps.core.models import TaskRun
from apps.credentials.models import Credential
from apps.notifications.models import Notification
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated(settings, tmp_path, monkeypatch):
    cache.clear()
    settings.BACKUP_DIR = tmp_path / "respaldos"
    settings.VERSION_FILE = tmp_path / "version"
    settings.PREV_INFO_FILE = tmp_path / "prev.info"
    settings.PRIVATE_COURSES_DIR = tmp_path / "cursos"
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(admin_center, "public_door_up", lambda: False)
    yield
    cache.clear()


def center(admin_person):
    return tailscale_client(admin_person.login).get("/administracion/").content.decode()


# --- record_run ----------------------------------------------------------------------------------------------------


def test_a_run_creates_one_row_and_a_second_run_updates_it():
    with taskruns.record_run("tarea_de_prueba") as run:
        run.summary = "3 cosas"
    row = TaskRun.objects.get(name="tarea_de_prueba")
    assert row.ok is True and row.summary == "3 cosas"
    assert row.started_at <= row.finished_at
    first = row.finished_at
    with taskruns.record_run("tarea_de_prueba") as run:
        run.summary = "5 cosas"
    assert TaskRun.objects.filter(name="tarea_de_prueba").count() == 1
    row = TaskRun.objects.get(name="tarea_de_prueba")
    assert row.summary == "5 cosas" and row.finished_at >= first


def test_a_failing_task_is_marked_failed_and_the_exception_still_propagates():
    with pytest.raises(ValueError, match="detalle privado"):
        with taskruns.record_run("rota") as run:
            run.summary = "2 hechas"
            raise ValueError("detalle privado de ana@example.com")
    row = TaskRun.objects.get(name="rota")
    assert row.ok is False
    assert row.summary == "Falló (ValueError). 2 hechas"
    assert "ana@example.com" not in row.summary and "detalle privado" not in row.summary


def test_a_failure_to_record_never_makes_the_task_fail(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("base bloqueada")

    monkeypatch.setattr(TaskRun.objects, "update_or_create", boom)
    done = []
    with taskruns.record_run("x") as run:
        run.summary = "ok"
        done.append(1)
    assert done == [1]
    with pytest.raises(KeyError):  # y la excepción de la tarea sigue siendo la suya
        with taskruns.record_run("x"):
            raise KeyError("k")


def test_disabled_records_nothing():
    with taskruns.record_run("seca", enabled=False):
        pass
    assert not TaskRun.objects.exists()


def test_summaries_are_one_short_line_without_emails():
    text = taskruns._clean("ana@example.com\n  entró " + "x" * 400)
    assert "@" not in text and "\n" not in text and len(text) == taskruns.SUMMARY_MAX


# --- los comandos de siempre registran su ejecución ---------------------------------------------------------------


def test_check_expirations_records_a_run_with_only_figures(member, lead):
    Credential.objects.create(
        owner=member,
        title="Curso de Ana Pérez",
        status="verified",
        expires_on=timezone.localdate() + timedelta(days=5),
        file="a.pdf",
    )
    call_command("check_expirations", verbosity=0)
    run = TaskRun.objects.get(name="check_expirations")
    assert run.ok is True and run.summary == "1 por vencer · 0 vencidas · 0 personas recalculadas"
    assert "Ana" not in run.summary and "@" not in run.summary
    assert Notification.objects.filter(kind="credential_expiring").exists()  # lo de siempre sigue


def test_check_expirations_output_is_unchanged(capsys):
    call_command("check_expirations")
    assert "Por vencer: 0 · vencidas: 0 · personas recalculadas: 0" in capsys.readouterr().out


def test_teo_seguimiento_and_reindex_record_runs():
    call_command("teo_seguimiento", verbosity=0)
    call_command("reindex_assistant", verbosity=0)
    assert TaskRun.objects.get(name="teo_seguimiento").summary.endswith("resúmenes a responsables")
    assert TaskRun.objects.get(name="reindex_assistant").summary.endswith("filas")


def test_seed_catalog_records_but_a_dry_run_does_not():
    call_command("seed_catalog", "--dry-run", verbosity=0)
    assert not TaskRun.objects.filter(name="seed_catalog").exists()
    call_command("seed_catalog", verbosity=0)
    run = TaskRun.objects.get(name="seed_catalog")
    assert run.ok is True and run.summary.endswith("rutas cargadas")


def test_private_courses_records_and_a_failure_keeps_its_error(settings):
    call_command("cargar_cursos_privados", verbosity=0)
    assert TaskRun.objects.get(name="cargar_cursos_privados").summary == "Carpeta no instalada"
    call_command("seed_catalog", verbosity=0)
    bad = settings.PRIVATE_COURSES_DIR / "una-ruta"
    bad.mkdir(parents=True)
    (bad / "ruta.json").write_text('{"slug": "otra-cosa"}')
    with pytest.raises(CommandError):
        call_command("cargar_cursos_privados", verbosity=0, stderr=io.StringIO())
    run = TaskRun.objects.get(name="cargar_cursos_privados")
    assert run.ok is False and run.summary.startswith("Falló (CommandError).")


def test_revisar_enlaces_records_a_run(admin_person, tmp_path):
    call_command("revisar_enlaces", "--limite", "2", "--salida", str(tmp_path), verbosity=0)
    run = TaskRun.objects.get(name="revisar_enlaces")
    assert run.ok is True and "enlaces internos rotos" in run.summary


def test_a_failed_systemd_unit_still_alerts_the_leads(lead):
    call_command("avisar_fallo", "centro-expiry.service", verbosity=0)
    assert Notification.objects.filter(kind="task_failed", recipient=lead).count() == 1


# --- el estado en el Centro ----------------------------------------------------------------------------------


def run_at(name, hours_ago, *, ok=True, summary=""):
    moment = timezone.now() - timedelta(hours=hours_ago)
    return TaskRun.objects.update_or_create(
        name=name,
        defaults={"started_at": moment, "finished_at": moment, "ok": ok, "summary": summary},
    )[0]


def check(label):
    status = admin_center.server_status()
    tasks = next(g for g in status["groups"] if g["label"] == "Tareas")["checks"]
    return next(c for c in tasks if c.label.startswith(label))


def test_no_record_yet_says_so():
    for label in ("Revisión de vencimientos", "Seguimiento de Nala", "Revisión de enlaces"):
        found = check(label)
        assert found.state == "none" and found.text == "Sin registro todavía."


def test_a_recent_success_is_ok_with_its_figures():
    run_at("check_expirations", 3, summary="2 por vencer")
    found = check("Revisión de vencimientos")
    assert found.state == "ok" and found.text.startswith("Corrió ")
    assert found.text.endswith("2 por vencer.")
    assert "todos los días a las 07:00" in found.label


def test_a_stale_run_is_late():
    run_at("check_expirations", 30)
    found = check("Revisión de vencimientos")
    assert found.state == "warn" and found.text.startswith("Atrasada: última")
    run_at("teo_seguimiento", 7 * 24)  # una semana: dentro de su tolerancia de 8 días
    assert check("Seguimiento de Nala").state == "ok"
    TaskRun.objects.filter(name="teo_seguimiento").update(
        finished_at=timezone.now() - timedelta(days=9)
    )
    assert check("Seguimiento de Nala").state == "warn"


def test_manual_tasks_are_never_late():
    run_at("revisar_enlaces", 24 * 90, summary="0 enlaces internos rotos")
    found = check("Revisión de enlaces")
    assert found.state == "ok" and "0 enlaces internos rotos" in found.text


def test_a_failure_notice_after_the_last_success_is_shown(lead):
    run_at("check_expirations", 30)
    call_command("avisar_fallo", "centro-expiry.service", verbosity=0)
    found = check("Revisión de vencimientos")
    assert found.state == "warn" and found.text.startswith("Falló el")
    run_at("check_expirations", 0)  # una corrida buena posterior limpia el aviso
    Notification.objects.update(created_at=timezone.now() - timedelta(hours=5))
    assert check("Revisión de vencimientos").state == "ok"


def test_a_failed_run_with_no_notice_is_a_warning():
    run_at("check_expirations", 2, ok=False, summary="Falló (ValueError).")
    found = check("Revisión de vencimientos")
    assert found.state == "warn" and found.text.startswith("Falló el")


def test_an_interrupted_run_is_flagged_after_two_hours():
    TaskRun.objects.create(
        name="seed_catalog", started_at=timezone.now() - timedelta(hours=3), ok=None
    )
    assert "no terminó" in check("Carga del catálogo").text
    TaskRun.objects.filter(name="seed_catalog").update(started_at=timezone.now())
    assert check("Carga del catálogo").text == "En curso."


def test_the_backup_row_comes_from_the_files_and_does_not_count_twice(settings):
    settings.BACKUP_DIR.mkdir()
    old = settings.BACKUP_DIR / "db-2026-10-01.sqlite3"
    old.write_bytes(b"x")
    stamp = (timezone.now() - timedelta(days=3)).timestamp()
    os.utime(old, (stamp, stamp))
    backup = check("Respaldo diario")
    assert backup.state == "warn" and backup.counts is False
    status = admin_center.server_status()
    assert status["warnings"] == sum(
        1 for g in status["groups"] for c in g["checks"] if c.state == "warn" and c.counts
    )


def test_a_backup_failure_notice_is_a_warning_on_the_backup_row(lead, settings):
    settings.BACKUP_DIR.mkdir()
    fresh = settings.BACKUP_DIR / f"db-{timezone.localdate().isoformat()}.sqlite3"
    fresh.write_bytes(b"x")
    stamp = (timezone.now() - timedelta(hours=20)).timestamp()
    os.utime(fresh, (stamp, stamp))
    call_command("avisar_fallo", "centro-backup.service", verbosity=0)
    status = admin_center.server_status()
    row = next(g for g in status["groups"] if g["label"] == "Respaldo")["checks"][0]
    assert row.state == "warn" and "El último intento falló" in row.text


def test_the_tasks_block_reads_runs_and_failures_in_two_queries():
    for i, name in enumerate(("check_expirations", "teo_seguimiento", "revisar_enlaces")):
        run_at(name, i)
    with CaptureQueriesContext(connection) as ctx:
        admin_center._task_checks({"db": None}, admin_center.task_failures())
    assert len(ctx) == 2


def test_the_page_shows_the_tasks_and_the_card_counts_their_warnings(admin_person):
    run_at("check_expirations", 40)
    html = center(admin_person)
    assert "Revisión de vencimientos (todos los días a las 07:00):</b> Atrasada: última" in html
    assert "Seguimiento de Nala (los lunes a las 09:00):</b> Sin registro todavía." in html
    cards = {c.key: c for c in admin_center.situation("admin", server=admin_center.server_status())}
    assert cards["server"].warn
    assert "ejecuciones" not in html  # nada de internals


def test_the_summaries_shown_carry_no_names_or_emails(admin_person, member):
    run_at("check_expirations", 1, summary="1 por vencer · 0 vencidas")
    html = center(admin_person)
    assert member.login not in html.split("<main")[1]
