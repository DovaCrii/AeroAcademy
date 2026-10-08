import configparser
import json
import logging
import sqlite3
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import Person
from apps.community.models import Note
from apps.core import legacy
from apps.gamification import game
from apps.notifications.models import Notification
from apps.paths.models import LearningPath, Level, Milestone, QuizQuestion, SharedItem
from apps.progress.models import MilestoneCheck, PathGoal, QuizAnswer
from apps.team.models import SharedCheck
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db
FORMA = "forma-revit"
DEPLOY = Path(settings.BASE_DIR) / "deploy"


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def keys():
    path = LearningPath.objects.get(slug=FORMA)
    ms = list(Milestone.objects.filter(path=path, retired=False).order_by("level__order", "order"))
    qs = list(
        QuizQuestion.objects.filter(path=path, retired=False).order_by("level__order", "order")
    )
    return path, ms, qs


@pytest.fixture
def legacy_db(tmp_path):
    path, ms, qs = keys()
    goal = path.extras.filter(kind="certification_goal").first().data["title"]
    db = tmp_path / "ruta.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE people(id TEXT PRIMARY KEY, name TEXT, pic TEXT, last_seen INTEGER);
        CREATE TABLE progress(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated INTEGER);
        CREATE TABLE notes(id TEXT PRIMARY KEY, author TEXT, lv TEXT, res INTEGER, type TEXT, text TEXT, parent TEXT, ts INTEGER);
        CREATE TABLE shared(key TEXT PRIMARY KEY, by TEXT, ts INTEGER);
        """
    )
    level_code = ms[0].level.code
    con.executemany(
        "INSERT INTO people VALUES(?,?,?,?)",
        [
            ("Ana@Lev.cl", "Ana Pérez", "https://pic.example/a.png", 1),
            ("luis@lev.cl", "Luis Soto", "javascript:alert(1)", 2),
        ],
    )
    data_ana = {
        "checks": {ms[0].key: True, ms[1].key: True, "zz-t99": True, ms[2].key: False},
        "quiz": {qs[0].key: qs[0].answer_index, "zz-q9": 1, qs[1].key: 99},
        "certGoal": goal,
    }
    con.execute("INSERT INTO progress VALUES(?,?,?)", ("ana@lev.cl", json.dumps(data_ana), 5))
    con.execute("INSERT INTO progress VALUES(?,?,?)", ("luis@lev.cl", "{no es json", 5))
    con.executemany(
        "INSERT INTO notes VALUES(?,?,?,?,?,?,?,?)",
        [
            (
                "n1",
                "ana@lev.cl",
                level_code,
                0,
                "works",
                "Funcionó muy bien",
                None,
                1_700_000_000_000,
            ),
            ("n2", "luis@lev.cl", "general", -1, "", "Nota sin tipo", None, 1_700_000_100_000),
            (
                "n3",
                "luis@lev.cl",
                level_code,
                -1,
                "ask",
                "Respuesta a la nota",
                "n1",
                1_700_000_200_000,
            ),
            ("n4", "ana@lev.cl", "general", -1, "tip", "Huérfana", "no-existe", 1_700_000_300_000),
            ("n5", "ana@lev.cl", "general", -1, "tip", "   ", None, 1_700_000_400_000),
            (
                "n6",
                "nueva@lev.cl",
                "general",
                -1,
                "fails",
                "De alguien nuevo",
                None,
                1_700_000_500_000,
            ),
        ],
    )
    con.executemany(
        "INSERT INTO shared VALUES(?,?,?)",
        [
            ("kit0-1", "ana@lev.cl", 1_700_000_000_000),
            ("ph1-0", "luis@lev.cl", 1_700_000_100_000),
            ("kit9-9", "ana@lev.cl", 1),
        ],
    )
    con.commit()
    con.close()
    return db


def test_import_creates_people_progress_notes_and_shared(legacy_db):
    summary = legacy.import_legacy(legacy_db)
    assert summary["checks"] == 2 and summary["quiz"] == 1 and summary["goals"] == 1
    assert summary["notes"] == 4 and summary["shared"] == 2 and summary["people"] == 3
    ana = Person.objects.get(login="ana@lev.cl")  # el correo se normaliza
    assert (
        ana.display_name == "Ana Pérez"
        and ana.status == "approved"
        and ana.avatar_url.startswith("https://")
    )
    assert Person.objects.get(login="luis@lev.cl").avatar_url == ""  # una URL no válida no pasa
    assert MilestoneCheck.objects.filter(person=ana).count() == 2
    assert (
        QuizAnswer.objects.filter(person=ana).count() == 1
        and PathGoal.objects.filter(person=ana).exists()
    )
    assert SharedCheck.objects.get(item__key="kit0-1").checked_by == ana
    skipped = " | ".join(summary["skipped"])
    for expected in ("zz-t99", "zz-q9", "kit9-9", "JSON inválido", "su nota ya no existe", "vacía"):
        assert expected in skipped


def test_notes_keep_dates_types_levels_and_replies(legacy_db):
    legacy.import_legacy(legacy_db)
    first = Note.objects.get(legacy_id="n1")
    reply = Note.objects.get(legacy_id="n3")
    assert first.type == "works" and first.level is not None and first.created_at.year == 2023
    assert reply.type == "reply" and reply.parent == first and reply.level == first.level
    assert (
        Note.objects.get(legacy_id="n2").type == "tip"
        and Note.objects.get(legacy_id="n2").level is None
    )
    assert Note.objects.get(legacy_id="n6").author.login == "nueva@lev.cl"
    assert not Note.objects.filter(legacy_id__in=["n4", "n5"]).exists()


def test_import_is_idempotent(legacy_db):
    legacy.import_legacy(legacy_db)
    counts = (
        Person.objects.count(),
        MilestoneCheck.objects.count(),
        QuizAnswer.objects.count(),
        Note.objects.count(),
        SharedCheck.objects.count(),
    )
    xp = {p.pk: game.total_xp(p) for p in Person.objects.all()}
    again = legacy.import_legacy(legacy_db)
    assert (
        again["people"],
        again["checks"],
        again["quiz"],
        again["goals"],
        again["notes"],
        again["shared"],
    ) == (0, 0, 0, 0, 0, 0)
    assert counts == (
        Person.objects.count(),
        MilestoneCheck.objects.count(),
        QuizAnswer.objects.count(),
        Note.objects.count(),
        SharedCheck.objects.count(),
    )
    assert xp == {p.pk: game.total_xp(p) for p in Person.objects.all()}


def test_imported_progress_gives_xp_but_notes_do_not_and_nobody_is_spammed(legacy_db, lead):
    before = Notification.objects.count()
    legacy.import_legacy(legacy_db)
    ana = Person.objects.get(login="ana@lev.cl")
    assert game.total_xp(ana) >= 10 * 2 + 5  # 2 misiones + 1 pregunta (más rachas o capítulos)
    assert "primera-luz" in game.unlocked_badges(ana)
    assert not ana.xp_events.filter(kind="note").exists()
    assert not Notification.objects.filter(kind="person_pending").exists()
    assert Notification.objects.exclude(kind__in=["badge", "level_up"]).count() == before


def test_existing_people_and_manual_marks_are_respected(legacy_db, member):
    ana = Person.objects.get(pk=member.pk)
    ana.login = "ana@lev.cl"
    ana.display_name = "Nombre ya elegido"
    ana.save()
    _, ms, _ = keys()
    MilestoneCheck.objects.create(person=ana, milestone=ms[0])
    summary = legacy.import_legacy(legacy_db)
    ana.refresh_from_db()
    assert (
        ana.display_name == "Nombre ya elegido"
        and MilestoneCheck.objects.filter(person=ana).count() == 2
    )
    assert summary["checks"] == 1


def test_dry_run_changes_nothing(legacy_db, capsys):
    call_command("import_legacy", db=str(legacy_db), dry_run=True)
    out = capsys.readouterr().out
    assert "[dry-run]" in out and "omitido" in out
    assert not Note.objects.exists() and not SharedCheck.objects.exists()
    assert not Person.objects.filter(login="ana@lev.cl").exists()


def test_command_reports_and_fails_cleanly(legacy_db, tmp_path, capsys):
    call_command("import_legacy", db=str(legacy_db))
    assert "Importado" in capsys.readouterr().out and Note.objects.count() == 4
    with pytest.raises(CommandError, match="No existe la base"):
        call_command("import_legacy", db=str(tmp_path / "nada.db"))
    with pytest.raises(CommandError, match="No existe la ruta"):
        call_command("import_legacy", db=str(legacy_db), path="no-existe")


def test_a_failure_rolls_everything_back(legacy_db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("falla a mitad")

    monkeypatch.setattr(legacy, "_import_shared", boom)
    with pytest.raises(RuntimeError):
        legacy.import_legacy(legacy_db)
    assert not Note.objects.exists() and not MilestoneCheck.objects.exists()


def test_the_legacy_database_is_opened_read_only(legacy_db):
    before = legacy_db.read_bytes()
    legacy.import_legacy(legacy_db)
    assert legacy_db.read_bytes() == before


def test_empty_legacy_database_is_fine(tmp_path):
    db = tmp_path / "vacia.db"
    sqlite3.connect(db).close()
    summary = legacy.import_legacy(db)
    assert summary["notes"] == 0 and summary["people"] == 0


def test_levels_in_legacy_codes_exist():
    assert Level.objects.filter(path__slug=FORMA, code="n0").exists()
    assert SharedItem.objects.filter(path__slug=FORMA, key="kit0-1").exists()


# --- salud, correo y despliegue --------------------------------------------------------------------------------------


def test_healthz_answers_only_from_the_local_proxy_without_identity():
    local = tailscale_client("", remote_addr="127.0.0.1")
    response = local.get("/healthz")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert tailscale_client("", remote_addr="10.1.2.3").get("/healthz").status_code == 403
    assert local.get("/").status_code == 401  # lo demás sigue exigiendo identidad


def test_email_hook_logs_without_content(member, caplog):
    from apps.notifications import services

    with caplog.at_level(logging.INFO, logger="apps.notifications.services"):
        services.notify(member, "x", "Título secreto", "Cuerpo secreto", key="k")
        services.notify(member, "x", "Otro secreto")
    text = caplog.text
    assert "email-hook" in text and "secreto" not in text and member.login not in text


def test_deploy_files_exist_and_are_consistent():
    for name in (
        "install.sh",
        "backup.sh",
        "centro.service",
        "centro-backup.service",
        "centro-backup.timer",
        "centro-expiry.service",
        "centro-expiry.timer",
    ):
        assert (DEPLOY / name).is_file(), name
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert (
        "\r" not in install
        and install.startswith("#!/usr/bin/env bash")
        and "set -euo pipefail" in install
    )
    for line in install.splitlines():
        code = line.split("#", 1)[0]
        if not code.strip().startswith("echo"):  # los avisos al operador pueden nombrarlo
            assert "tailscale funnel" not in code, "nunca se usa funnel"
    assert (
        "tailscale serve --bg" in install
        and "healthz" in install
        and "migrate" in install
        and "collectstatic" in install
    )
    assert (
        "seed_catalog" in install and "config.settings.prod" in install and "chmod 640" in install
    )


def test_systemd_units_parse_and_match_the_architecture():
    for name in (
        "centro.service",
        "centro-backup.service",
        "centro-expiry.service",
        "centro-backup.timer",
        "centro-expiry.timer",
    ):
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        cp.optionxform = str
        cp.read_string((DEPLOY / name).read_text(encoding="utf-8"))
        assert cp.sections(), name
    service = (DEPLOY / "centro.service").read_text(encoding="utf-8")
    assert (
        "127.0.0.1:8010" in service
        and "EnvironmentFile=/etc/centro/env" in service
        and "NoNewPrivileges=true" in service
    )
    assert "check_expirations" in (DEPLOY / "centro-expiry.service").read_text(encoding="utf-8")
    backup = (DEPLOY / "backup.sh").read_text(encoding="utf-8")
    assert (
        ".backup" in backup
        and "media" in backup
        and "-mtime +30" in backup
        and "umask 077" in backup
    )


def test_no_secret_in_the_deploy_files():
    for path in DEPLOY.iterdir():
        if (
            path.name == "centro.env"
        ):  # la configuración real de la persona: ignorada por git, sí lleva la clave
            continue
        text = path.read_text(encoding="utf-8")
        assert "nvapi-" not in text
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert "NIM_API_KEY=\n" in install  # la clave queda vacía: la pone la persona


def test_the_installer_is_safe_for_a_shared_vm():
    """La VM también corre AeroControl (127.0.0.1:8000 y los puertos HTTPS con Funnel): no se les toca."""
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert (
        'PORT="${AEROACADEMY_PORT:-8010}"' in install
        and 'PUBLISH="${AEROACADEMY_PUBLISH:-node}"' in install
    )
    assert 'tailscale serve --bg "$PORT"' not in install
    assert "tailscale serve reset" not in install and "tailscale serve off" not in install
    assert "UV_PYTHON_INSTALL_DIR" in install  # el intérprete de uv no queda en /root
    assert "ya lo usa otro servicio" in install and "ya sirve otra cosa" in install
    assert "127.0.0.1:8010" in (DEPLOY / "centro.service").read_text(encoding="utf-8")
    code = [line for line in install.splitlines() if not line.strip().startswith("#")]
    assert not any(
        "8000" in line for line in code
    )  # el 8000 es de AeroControl: solo se nombra en comentarios


def test_the_default_is_its_own_tailscale_node_not_the_main_one():
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert (
        'TS=(tailscale --socket="$NODE_SOCK")' in install
        and "/run/tailscale-aeroacademy/tailscaled.sock" in install
    )
    assert (
        '"${TS[@]}" serve --bg --https=443' in install
    )  # el nodo propio sirve en su 443, no en el de AeroControl
    assert "up --hostname=" in install and "AEROACADEMY_TS_AUTHKEY" in install
    unit = (DEPLOY / "tailscaled-aeroacademy.service").read_text(encoding="utf-8")
    assert "--statedir=/var/lib/tailscale-aeroacademy" in unit  # guarda estado y certificados
    assert "--socket=/run/tailscale-aeroacademy/tailscaled.sock" in unit
    assert (
        "--tun=userspace-networking" in unit and "--port=41642" in unit
    )  # no choca con el tailscaled del sistema
    assert "tailscale-aeroacademy" in unit and "funnel" not in unit.lower()


def test_the_env_file_in_the_repo_wins_and_keeps_the_secret_key():
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert 'cp "$SRC/deploy/centro.env" "$ENV_FILE"' in install and '"$ENV_FILE.bak"' in install
    assert 'set_env SECRET_KEY "${OLD_SECRET:-$(new_secret)}"' in install
    assert 'set_env ALLOWED_HOSTS "$DNSNAME"' in install  # el nombre real del nodo manda


def test_the_env_template_carries_no_secret_and_the_real_file_is_ignored():
    text = (DEPLOY / "centro.env.plantilla").read_text(encoding="utf-8")
    assert "\nNIM_API_KEY=\n" in text and "nvapi-" not in text
    assert "PUBLIC_HTTPS_PORT=443" in text and "aeroacademy.tailccd107.ts.net" in text


def test_the_installer_does_not_copy_a_file_onto_itself_and_pins_python():
    """Error real en p340: tras `cd "$APP"`, `install deploy/backup.sh "$APP/deploy/backup.sh"` era el mismo archivo."""
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert 'install -m 755 deploy/backup.sh "$APP/deploy/backup.sh"' not in install
    assert 'chmod 755 "$APP/deploy/backup.sh"' in install
    assert "export UV_PYTHON=3.12" in install
    # todo `install` relativo escribe a /etc: nunca a una ruta dentro de $APP
    for line in install.splitlines():
        if line.strip().startswith("install ") and "deploy/" in line:
            assert "/etc/systemd/system" in line or "$unit" in line, line


def test_the_installer_issues_the_certificate_up_front():
    """Error real en p340: el navegador veía ERR_CONNECTION_CLOSED en el nodo nuevo; el certificado se emite al instalar."""
    install = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    serve = install.index('"${TS[@]}" serve --bg --https=443')
    cert = install.index('"${TS[@]}" cert --cert-file')
    assert serve < cert < install.index('echo "    Dirección: https://$HC_HOST"\n    ;;')
    assert "HTTPS Certificates" in install and "diagnostico.sh" in install
