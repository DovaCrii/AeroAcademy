"""Pruebas de `deploy/actualizar.sh` (con stubs de git, sqlite3, curl, systemctl e install.sh) y de `tools/desplegar.ps1`.

El script real corre en la VM; aquí se ejecuta en una carpeta temporal con comandos falsos en el PATH y las
variables de entorno de prueba (APP_DIR, BACKUP_DIR, INSTALL_SCRIPT…). Ninguna prueba toca una máquina real.
"""

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings

BASE = Path(settings.BASE_DIR)
SCRIPT = BASE / "deploy" / "actualizar.sh"
PS1 = BASE / "tools" / "desplegar.ps1"

# El script es de Linux (rsync, flock, stat -c); en Windows `bash` es WSL y no ve las rutas: solo en Linux/macOS con GNU.
needs_bash = pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("bash") or not shutil.which("rsync"),
    reason="requiere Linux con bash y rsync",
)

GIT = r"""#!/usr/bin/env bash
echo "git $*" >> "$STUB/calls.log"
args=("$@"); [ "${args[0]}" = "-C" ] && args=("${args[@]:2}")
case "${args[0]}" in
  status) cat "$STUB/dirty" 2>/dev/null || true ;;
  rev-parse) cat "$STUB/head" ;;
  fetch) [ ! -e "$STUB/fetch_fails" ] ;;
  pull) [ -e "$STUB/pull_fails" ] && exit 1; cp "$STUB/newhead" "$STUB/head" ;;
  log) echo "abc1234 Cambio de prueba" ;;
  reset) echo "${args[2]}" > "$STUB/head" ;;
esac
"""
SQLITE = r"""#!/usr/bin/env bash
echo "sqlite3 $*" >> "$STUB/calls.log"
args=("$@")
if [ "${args[0]}" = "-cmd" ]; then
  db="${args[2]}"; cmd="${args[3]}"
  dest="${cmd#.backup \'}"; dest="${dest%\'}"
  cp "$db" "$dest"
else
  cat "$STUB/migcount"
fi
"""
CURL = r"""#!/usr/bin/env bash
echo "curl $*" >> "$STUB/calls.log"
grep -q good "$APP_DIR/VERSION"
"""
SYSTEMCTL = r"""#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB/calls.log"
if [ "$1" = "is-active" ]; then
  [ "$3" = "centro-public" ] && exit 3
  exit 0
fi
exit 0
"""
# El «instalador»: pone la versión nueva (buena o mala) y, si se pide, «migra» (cambia la base y el contador).
INSTALL = r"""#!/usr/bin/env bash
echo "install PUBLIC_FUNNEL=${PUBLIC_FUNNEL:-sin} EXTRA=${EXTRA_FLAG:-sin}" >> "$STUB/calls.log"
[ -e "$STUB/install_fails" ] && exit 1
cat "$STUB/new_version" > "$APP_DIR/VERSION"
echo "codigo nuevo" > "$APP_DIR/app.py"
if [ -e "$STUB/migrates" ]; then echo db-v2 > "$DB_PATH"; echo 6 > "$STUB/migcount"; fi
exit 0
"""


@pytest.fixture
def box(tmp_path):
    """Una «VM» de mentira: app instalada (versión buena), base v1 y comandos falsos."""
    stub = tmp_path / "stub"
    bin_dir = tmp_path / "bin"
    app = tmp_path / "opt" / "aeroacademy"
    for d in (stub, bin_dir, app, tmp_path / "var", tmp_path / "repo" / "deploy", tmp_path / "bk"):
        d.mkdir(parents=True, exist_ok=True)
    for name, body in (("git", GIT), ("sqlite3", SQLITE), ("curl", CURL), ("systemctl", SYSTEMCTL)):
        f = bin_dir / name
        f.write_text(body, encoding="utf-8")
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    install = tmp_path / "repo" / "deploy" / "install.sh"
    install.write_text(INSTALL, encoding="utf-8")
    install.chmod(install.stat().st_mode | stat.S_IEXEC)
    (app / "VERSION").write_text("good-1\n", encoding="utf-8")
    (app / "app.py").write_text("codigo viejo\n", encoding="utf-8")
    (app / "staticfiles").mkdir()
    (app / "staticfiles" / "x.css").write_text("css", encoding="utf-8")
    db = tmp_path / "var" / "db.sqlite3"
    db.write_text("db-v1\n", encoding="utf-8")
    (stub / "head").write_text("aaaaaaa\n", encoding="utf-8")
    (stub / "newhead").write_text("bbbbbbb\n", encoding="utf-8")
    (stub / "migcount").write_text("5\n", encoding="utf-8")
    (stub / "new_version").write_text("good-2\n", encoding="utf-8")
    env_file = tmp_path / "env"
    env_file.write_text(
        "SECRET_KEY=no-sale-en-la-salida\nALLOWED_HOSTS=nodo.example.ts.net\n", encoding="utf-8"
    )

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "STUB": str(stub),
        "APP_DIR": str(app),
        "PREV_DIR": str(tmp_path / "opt" / "aeroacademy.prev"),
        "BACKUP_DIR": str(tmp_path / "bk"),
        "DB_PATH": str(db),
        "ENV_FILE": str(env_file),
        "INSTALL_SCRIPT": str(install),
        "REPO_DIR": str(tmp_path / "repo"),
        "LOCK_FILE": str(tmp_path / "lock"),
        "ACTUALIZAR_SIN_ROOT": "1",
        "HEALTH_RETRIES": "2",
        "HEALTH_SLEEP": "0",
    }
    env.pop("PUBLIC_FUNNEL", None)

    class Box:
        pass

    b = Box()
    b.stub, b.app, b.db, b.env, b.tmp = stub, app, db, env, tmp_path
    b.prev = tmp_path / "opt" / "aeroacademy.prev"

    def run(*args, extra=None, stdin=subprocess.DEVNULL):
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            env={**env, **(extra or {})},
            capture_output=True,
            text=True,
            stdin=stdin,
            timeout=60,
        )

    b.run = run
    b.calls = lambda: (
        (stub / "calls.log").read_text(encoding="utf-8") if (stub / "calls.log").exists() else ""
    )
    return b


@needs_bash
def test_update_success_path(box):
    cp = box.run(extra={"EXTRA_FLAG": "x", "PUBLIC_FUNNEL": "1"})
    out = cp.stdout + cp.stderr
    assert cp.returncode == 0, out
    assert (box.app / "VERSION").read_text().strip() == "good-2"
    assert (box.prev / "VERSION").read_text().strip() == "good-1"  # instantánea del código viejo
    assert not (box.prev / "staticfiles").exists()  # no se copian estáticos
    backups = list(box.tmp.joinpath("bk").glob("pre-actualizar-*.sqlite3"))
    assert len(backups) == 1 and backups[0].read_text() == "db-v1\n"
    assert "aaaaaaa" in out and "bbbbbbb" in out and "Cambio de prueba" in out
    assert (
        "PUBLIC_FUNNEL=1" in box.calls() and "EXTRA=x" in box.calls()
    )  # el entorno pasa al instalador
    assert " pull --ff-only" in box.calls()
    assert "no-sale-en-la-salida" not in out  # nunca imprime secretos
    info = (box.tmp / "opt" / "aeroacademy.prev.info").read_text()
    assert "migrations_before=5" in info and "commit_before=aaaaaaa" in info


@needs_bash
def test_backup_retention_keeps_the_last_five(box):
    bk = box.tmp / "bk"
    for i in range(7):
        (bk / f"pre-actualizar-20200101T00000{i}Z.sqlite3").write_text("viejo")
    assert box.run().returncode == 0
    names = sorted(p.name for p in bk.glob("pre-actualizar-*.sqlite3"))
    assert len(names) == 5
    assert "pre-actualizar-20200101T000000Z.sqlite3" not in names  # se van las más viejas


@needs_bash
def test_health_failure_rolls_back_code_without_touching_db_when_no_migration(box):
    (box.stub / "new_version").write_text("bad-2\n")
    cp = box.run()
    out = cp.stdout + cp.stderr
    assert cp.returncode == 1, out
    assert (box.app / "VERSION").read_text().strip() == "good-1"
    assert (box.app / "app.py").read_text() == "codigo viejo\n"
    assert box.db.read_text() == "db-v1\n"
    assert "no hubo migraciones" in out and "journalctl -u centro" in out
    assert (
        box.stub / "head"
    ).read_text().strip() == "aaaaaaa"  # el repositorio vuelve al commit instalado
    assert "systemctl restart centro" in box.calls()


@needs_bash
def test_health_failure_after_migration_restores_the_database(box):
    (box.stub / "new_version").write_text("bad-2\n")
    (box.stub / "migrates").write_text("")
    cp = box.run()
    out = cp.stdout + cp.stderr
    assert cp.returncode == 1, out
    assert (box.app / "VERSION").read_text().strip() == "good-1"
    assert box.db.read_text() == "db-v1\n"  # base de antes de migrar
    assert "BASE DE DATOS RESTAURADA" in out and "migraciones (5 -> 6)" in out
    assert "systemctl stop centro" in box.calls()


@needs_bash
def test_installer_failure_also_rolls_back(box):
    (box.stub / "install_fails").write_text("")
    cp = box.run()
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert (box.app / "VERSION").read_text().strip() == "good-1"
    assert "el instalador terminó con error" in cp.stderr


@needs_bash
def test_rollback_that_cannot_recover_exits_2(box):
    (box.stub / "new_version").write_text("bad-2\n")
    # El código «viejo» tampoco está sano: la reversa falla y se avisa con código 2.
    (box.app / "VERSION").write_text("bad-1\n")
    cp = box.run()
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "LA REVERSA TAMBIÉN FALLÓ" in cp.stderr


@needs_bash
def test_manual_revert_restores_code_and_db_with_flag(box):
    (box.stub / "migrates").write_text("")
    assert box.run().returncode == 0
    assert (box.app / "VERSION").read_text().strip() == "good-2" and box.db.read_text() == "db-v2\n"
    cp = box.run("--revertir", "--con-base")
    out = cp.stdout + cp.stderr
    assert cp.returncode == 0, out
    assert (box.app / "VERSION").read_text().strip() == "good-1"
    assert box.db.read_text() == "db-v1\n"
    assert (box.stub / "head").read_text().strip() == "aaaaaaa"


@needs_bash
def test_manual_revert_without_terminal_keeps_the_database(box):
    (box.stub / "migrates").write_text("")
    assert box.run().returncode == 0
    cp = box.run(
        "--revertir"
    )  # sin terminal ni --con-base: no se pierde nada de la base sin permiso
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (box.app / "VERSION").read_text().strip() == "good-1"
    assert box.db.read_text() == "db-v2\n"
    assert "NO se restauró" in cp.stderr


@needs_bash
def test_revert_without_snapshot_changes_nothing(box):
    cp = box.run("--revertir")
    assert cp.returncode == 3
    assert (box.app / "VERSION").read_text().strip() == "good-1"


@needs_bash
def test_only_check_does_not_change_anything(box):
    ok = box.run("--solo-comprobar")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "git " not in box.calls() and not box.prev.exists()
    (box.app / "VERSION").write_text("bad-1\n")
    ko = box.run("--solo-comprobar")
    assert ko.returncode == 1 and "journalctl -u centro" in ko.stderr
    assert "127.0.0.1:8010/healthz" in box.calls() and "Host: nodo.example.ts.net" in box.calls()


@needs_bash
def test_dirty_repo_or_bad_pull_stops_before_changing_anything(box):
    (box.stub / "dirty").write_text(" M archivo.py\n")
    cp = box.run()
    assert cp.returncode == 3 and "cambios sin confirmar" in cp.stderr
    (box.stub / "dirty").write_text("")
    (box.stub / "pull_fails").write_text("")
    cp = box.run()
    assert cp.returncode == 3 and "pull --ff-only" in cp.stderr
    assert (box.app / "VERSION").read_text().strip() == "good-1" and not box.prev.exists()


@needs_bash
def test_no_pull_uses_the_working_tree(box):
    cp = box.run("--sin-pull")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert " fetch " not in box.calls() and " pull " not in box.calls()


@needs_bash
def test_requires_root_without_the_test_override(box):
    if os.geteuid() == 0:
        pytest.skip("corre como root")
    cp = box.run(extra={"ACTUALIZAR_SIN_ROOT": "0"})
    assert cp.returncode == 3 and "sudo" in cp.stderr


# ── Pruebas estáticas (corren en cualquier sistema) ─────────────────────────────────────────────────────────────


def _bash_syntax(path):
    bash = shutil.which("bash")
    if not bash or sys.platform != "linux":
        pytest.skip("requiere bash en Linux")
    cp = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr


@pytest.mark.parametrize("path", sorted((BASE / "deploy").glob("*.sh")), ids=lambda p: p.name)
def test_deploy_scripts_have_valid_syntax(path):
    _bash_syntax(path)


def test_actualizar_script_conventions():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash") and "\r" not in text
    assert "set -euo pipefail" in text
    for flag in ("--solo-comprobar", "--revertir", "--sin-pull"):
        assert flag in text
    assert "http://127.0.0.1:$PORT/healthz" in text and "pull --ff-only" in text
    assert "sqlite3" in text and ".backup" in text and "pre-actualizar-" in text
    # no toca AeroControl ni el contenido de /etc/centro/env
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "aerocontrol" not in code.lower()
    assert 'echo "$SECRET' not in code and 'cat "$ENV_FILE"' not in code
    assert '>> "$ENV_FILE"' not in code and "sed -i" not in code


def test_manage_wires_reserved_words_and_keeps_manage_py():
    text = (BASE / "deploy" / "manage.sh").read_text(encoding="utf-8")
    assert "actualizar)" in text and "revertir)" in text and "actualizar.sh" in text
    assert 'manage.py "$@"' in text and "sudo -u centro" in text
    install = (BASE / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "/etc/centro/repo" in text and '"$ENV_DIR/repo"' in install


LITERAL_HOST = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])|\b[\w-]+\.ts\.net\b|ssh\s+[\w.-]+@[\w.<-]+",
    re.IGNORECASE,
)
ALLOWED_LITERALS = {"127.0.0.1", "0.0.0.0", "1.2.3.4"}


@pytest.mark.parametrize(
    "path",
    [*sorted((BASE / "deploy").glob("*.sh")), PS1, BASE / "deploy" / "vm.local.json.ejemplo"],
    ids=lambda p: p.name,
)
def test_no_real_host_ip_or_user_in_deploy_tooling(path):
    text = path.read_text(encoding="utf-8")
    for m in LITERAL_HOST.finditer(text):
        lit = m.group(0)
        if (
            lit in ALLOWED_LITERALS
            or re.search(r"[\w-]+\.ts\.net", lit)
            and ("example" in lit or "<" in lit)
        ):
            continue
        if lit.lower().startswith("ssh") and re.search(r"@(<|\$|%)", lit):
            continue
        if re.match(r"ssh\s+example@", lit):
            continue
        pytest.fail(f"{path.name}: literal sospechoso {lit!r}")


def test_privacy_scan_passes_on_the_new_files():
    cp = subprocess.run(
        [sys.executable, str(BASE / "tools" / "kit" / "privacy_scan.py"), "--root", str(BASE)],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_local_vm_config_is_ignored_and_example_is_a_placeholder():
    import json

    ignore = (BASE / ".gitignore").read_text(encoding="utf-8")
    assert "deploy/vm.local.json" in ignore.splitlines()
    example = json.loads((BASE / "deploy" / "vm.local.json.ejemplo").read_text(encoding="utf-8"))
    assert example["host"].startswith("<") and example["user"] == "example"
    cp = subprocess.run(
        ["git", "-C", str(BASE), "check-ignore", "-q", "deploy/vm.local.json"], capture_output=True
    )
    assert cp.returncode in (0, 128)  # 0 = ignorado (128 si no es un repo git, p. ej. un tarball)
    if cp.returncode == 128:
        pytest.skip("no es un repositorio git")


def test_powershell_script_parses_and_has_its_switches():
    text = PS1.read_text(encoding="utf-8")
    for name in ("SoloComprobar", "Revertir", "SinPrivados", "DryRun"):
        assert f"${name}" in text
    assert "deploy/vm.local.json" in text and "aeroacademy actualizar" in text and "ssh" in text
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("pwsh no está instalado")
    cp = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{PS1}',[ref]$t,[ref]$e); if($e.Count){{$e|Out-String;exit 1}}",
        ],
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_docs_describe_the_one_command_update():
    prod = (BASE / "docs" / "PRODUCCION.md").read_text(encoding="utf-8")
    oper = (BASE / "docs" / "OPERACION.md").read_text(encoding="utf-8")
    for doc in (prod, oper):
        assert "aeroacademy actualizar" in doc and "PUBLIC_FUNNEL" in doc
    assert "desplegar.ps1" in prod and "--revertir" in prod
