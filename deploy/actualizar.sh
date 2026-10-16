#!/usr/bin/env bash
# Actualiza AeroAcademy en la VM con UN comando y reversa automática.
# Uso (desde el repositorio clonado, p. ej. ~/AeroAcademy):
#   sudo ./deploy/actualizar.sh [opciones]      ·      sudo aeroacademy actualizar [opciones]
#
# Opciones:
#   --solo-comprobar   solo mira la salud del servicio (no cambia nada)
#   --revertir         vuelve a la versión anterior guardada por la última actualización
#   --sin-pull         no hace git fetch/pull: usa el árbol de trabajo tal como está
#   --con-base         (con --revertir) restaura también la base de datos si la última actualización migró
#   --sin-base         (con --revertir) nunca restaura la base de datos
#
# Pasos: precondiciones (root, repo limpio) → fetch + pull --ff-only → instantánea del código instalado
# (/opt/aeroacademy → /opt/aeroacademy.prev) y respaldo consistente de SQLite (.backup) → deploy/install.sh
# (con tu entorno: PUBLIC_FUNNEL, AEROACADEMY_PORT, AEROACADEMY_TS_AUTHKEY…) → comprobación de salud.
# Si algo falla: restaura el código, reinicia, vuelve a comprobar y, SOLO si la actualización aplicó migraciones,
# restaura también la base respaldada (se pierde lo escrito entre el respaldo y la falla: minutos).
#
# Variables para pruebas o instalaciones no estándar (los valores por defecto son los de producción):
#   APP_DIR PREV_DIR BACKUP_DIR DB_PATH ENV_FILE INSTALL_SCRIPT REPO_DIR LOCK_FILE
#   AEROACADEMY_PORT AEROACADEMY_PUBLIC_PORT HEALTH_RETRIES HEALTH_SLEEP ACTUALIZAR_SIN_ROOT=1
#
# Salida: 0 = actualizado (o comprobado) · 1 = falló y se restauró la versión anterior · 2 = falló y la
# restauración también falló (intervención manual) · 3 = precondición no cumplida (no se cambió nada).
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SELF_DIR/.." && pwd)}"
APP_DIR="${APP_DIR:-/opt/aeroacademy}"
PREV_DIR="${PREV_DIR:-${APP_DIR}.prev}"
INFO_FILE="${PREV_DIR}.info"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/centro}"
DB_PATH="${DB_PATH:-/var/lib/centro/db.sqlite3}"
ENV_FILE="${ENV_FILE:-/etc/centro/env}"
INSTALL_SCRIPT="${INSTALL_SCRIPT:-$REPO_DIR/deploy/install.sh}"
LOCK_FILE="${LOCK_FILE:-/run/lock/aeroacademy-actualizar.lock}"
SERVICE_USER=centro
PORT="${AEROACADEMY_PORT:-8010}"
PUBLIC_PORT="${AEROACADEMY_PUBLIC_PORT:-8011}"
HEALTH_RETRIES="${HEALTH_RETRIES:-6}"
HEALTH_SLEEP="${HEALTH_SLEEP:-2}"
KEEP_BACKUPS=5
# Lo que NO se copia ni se restaura con el código (mismo criterio que install.sh): entorno, estáticos, datos.
EXCLUDES=(--exclude ".venv" --exclude ".uv-python" --exclude ".gunicorn" --exclude "__pycache__" --exclude ".git"
  --exclude "staticfiles" --exclude "db.sqlite3*" --exclude "media" --exclude ".env" --exclude "deploy/centro.env"
  --exclude "private")

MODE=actualizar
DO_PULL=1
DB_POLICY=ask
for arg in "$@"; do
  case "$arg" in
    --solo-comprobar) MODE=comprobar ;;
    --revertir) MODE=revertir ;;
    --sin-pull) DO_PULL=0 ;;
    --con-base) DB_POLICY=yes ;;
    --sin-base) DB_POLICY=no ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $arg (usa --help)" >&2; exit 3 ;;
  esac
done

say() { echo "==> $*"; }
note() { echo "    $*"; }
warn() { echo "    ! $*" >&2; }
die_pre() { echo "No se puede actualizar: $*" >&2; exit 3; }

IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then IS_ROOT=1; fi
if [ "$MODE" != comprobar ] && [ "$IS_ROOT" -ne 1 ] && [ "${ACTUALIZAR_SIN_ROOT:-0}" != 1 ]; then
  die_pre "ejecuta con sudo (sudo aeroacademy actualizar)."
fi

# git corre como la dueña del repositorio (no como root): así no cambia permisos ni choca con safe.directory.
GIT_AS=()
if [ "$IS_ROOT" -eq 1 ]; then
  REPO_OWNER="$(stat -c %U "$REPO_DIR" 2>/dev/null || echo root)"
  if [ "$REPO_OWNER" != root ]; then GIT_AS=(sudo -u "$REPO_OWNER"); fi
fi
g() { "${GIT_AS[@]}" git -C "$REPO_DIR" "$@"; }

# ── Salud ─────────────────────────────────────────────────────────────────────────────────────────────────────
env_value() { [ -f "$ENV_FILE" ] && grep "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true; }

health_once() {  # una pasada: /healthz local de la puerta de la tailnet (y de la pública si está activa) + systemd
  local host url_host=()
  host="$(env_value ALLOWED_HOSTS | cut -d, -f1)"
  if [ -n "$host" ]; then url_host=(-H "Host: $host"); fi
  systemctl is-active --quiet centro || return 1
  curl -fsS --max-time 10 "${url_host[@]}" "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 || return 1
  if systemctl is-active --quiet centro-public 2>/dev/null; then
    curl -fsS --max-time 10 "${url_host[@]}" "http://127.0.0.1:$PUBLIC_PORT/healthz" >/dev/null 2>&1 || return 1
  fi
}

health_check() {  # reintenta con espera creciente (HEALTH_SLEEP, 2×, 3×…)
  local i
  for i in $(seq 1 "$HEALTH_RETRIES"); do
    if health_once; then return 0; fi
    if [ "$i" -lt "$HEALTH_RETRIES" ]; then
      note "sin respuesta todavía (intento $i/$HEALTH_RETRIES); espero..."
      sleep "$((HEALTH_SLEEP * i))"
    fi
  done
  return 1
}

if [ "$MODE" = comprobar ]; then
  say "Comprobando la salud del servicio"
  if health_check; then
    note "servicio OK en 127.0.0.1:$PORT"
    exit 0
  fi
  echo "El servicio NO responde. Revisa: journalctl -u centro -n 100 --no-pager" >&2
  exit 1
fi

# ── Utilidades de datos ───────────────────────────────────────────────────────────────────────────────────────
mig_count() {  # migraciones aplicadas según la base (0 si aún no existe); «?» si no se pudo leer
  if [ ! -f "$DB_PATH" ]; then echo 0; return; fi
  sqlite3 "$DB_PATH" "SELECT count(*) FROM django_migrations;" 2>/dev/null || echo "?"
}

restart_services() {
  systemctl restart centro
  if systemctl is-active --quiet centro-public 2>/dev/null; then systemctl restart centro-public; fi
}

restore_code() {  # PREV_DIR → APP_DIR (sin tocar entorno virtual, estáticos ni datos)
  rsync -a --checksum --delete "${EXCLUDES[@]}" "$PREV_DIR"/ "$APP_DIR"/
  if [ "$IS_ROOT" -eq 1 ]; then
    chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" 2>/dev/null || true
    # El código viejo debe quedar con sus dependencias y estáticos: mejor esfuerzo, no impide la reversa.
    if [ -f "$APP_DIR/uv.lock" ] && command -v uv >/dev/null 2>&1; then
      (cd "$APP_DIR" && UV_PYTHON_INSTALL_DIR="$APP_DIR/.uv-python" UV_PYTHON=3.12 \
        UV_PROJECT_ENVIRONMENT="$APP_DIR/.venv" uv sync --frozen --no-dev >/dev/null 2>&1) \
        || warn "no se pudo resincronizar el entorno Python (uv sync); se sigue con el actual"
    fi
    if [ -x "$APP_DIR/.venv/bin/python" ] && [ -f "$ENV_FILE" ]; then
      (cd "$APP_DIR" && sudo -u "$SERVICE_USER" bash -c 'set -a; . "$1"; set +a; exec "$2" manage.py collectstatic --noinput' \
        _ "$ENV_FILE" "$APP_DIR/.venv/bin/python" >/dev/null 2>&1) \
        || warn "no se pudieron regenerar los estáticos (collectstatic)"
    fi
  fi
}

restore_db() {  # restore_db <respaldo>: con el servicio detenido; deja la base como estaba al respaldar
  local backup="$1"
  systemctl stop centro || true
  systemctl stop centro-public 2>/dev/null || true
  rm -f "$DB_PATH-wal" "$DB_PATH-shm"
  cp -f "$backup" "$DB_PATH"
  if [ "$IS_ROOT" -eq 1 ]; then chown "$SERVICE_USER:$SERVICE_USER" "$DB_PATH" 2>/dev/null || true; fi
  chmod 600 "$DB_PATH" 2>/dev/null || true
}

info_get() { [ -f "$INFO_FILE" ] && grep "^$1=" "$INFO_FILE" | head -n1 | cut -d= -f2- || true; }

repo_back_to() {  # deja el repositorio en el commit instalado antes (si está limpio); evita que `git log` mienta
  local commit="$1"
  if [ -z "$commit" ] || [ "$DO_PULL" -eq 0 ]; then return 0; fi
  if [ -n "$(g status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    warn "el repositorio tiene cambios; no se mueve de commit (git reset --hard $commit a mano)"
    return 0
  fi
  g reset --hard "$commit" >/dev/null 2>&1 && note "repositorio devuelto a $commit" \
    || warn "no se pudo devolver el repositorio a $commit"
}

# ── Reversa (la usan --revertir y el fallo automático) ────────────────────────────────────────────────────────
do_rollback() {  # do_rollback <base: yes|no|ask> ; devuelve 0 si el servicio quedó sano
  local want_db="$1" before after backup restored_db=0
  before="$(info_get migrations_before)"
  backup="$(info_get db_backup)"
  after="$(mig_count)"
  say "Restaurando el código anterior desde $PREV_DIR"
  restore_code
  if [ -n "$before" ] && [ "$before" != "?" ] && [ "$after" != "?" ] && [ "$after" != "$before" ]; then
    echo
    echo "    ############################################################"
    echo "    # La actualización aplicó migraciones ($before -> $after)."
    echo "    # El código anterior no entiende esa base."
    echo "    ############################################################"
    if [ "$want_db" = ask ]; then
      if [ -t 0 ]; then
        read -r -p "    ¿Restaurar la base respaldada (se pierde lo escrito desde entonces)? [s/N] " ans || ans=""
        case "$ans" in [sS]*) want_db=yes ;; *) want_db=no ;; esac
      else
        want_db=no
        warn "sin terminal para preguntar: no se restaura la base (usa --con-base)"
      fi
    fi
    if [ "$want_db" = yes ] && [ -f "$backup" ]; then
      say "Restaurando la base desde $backup"
      restore_db "$backup"
      restored_db=1
      note "BASE RESTAURADA: se perdió lo escrito en la academia desde el respaldo"
    elif [ "$want_db" = yes ]; then
      warn "no existe el respaldo $backup: la base NO se restauró"
    else
      warn "la base NO se restauró: el servicio puede fallar con el código anterior"
    fi
  fi
  say "Reiniciando servicios"
  restart_services || true
  REVERT_DB_RESTORED=$restored_db
  health_check
}

# ── Candado: una actualización a la vez ───────────────────────────────────────────────────────────────────────
if command -v flock >/dev/null 2>&1 && mkdir -p "$(dirname "$LOCK_FILE")" 2>/dev/null; then
  exec 9>"$LOCK_FILE"
  flock -n 9 || die_pre "ya hay otra actualización en curso."
fi

# ── Reversa manual ────────────────────────────────────────────────────────────────────────────────────────────
if [ "$MODE" = revertir ]; then
  [ -d "$PREV_DIR" ] || die_pre "no hay una versión anterior guardada en $PREV_DIR."
  OLD_COMMIT="$(info_get commit_before)"
  say "Revirtiendo a la versión anterior ${OLD_COMMIT:+($OLD_COMMIT)}"
  REVERT_DB_RESTORED=0
  if do_rollback "$DB_POLICY"; then
    repo_back_to "$OLD_COMMIT"
    say "Reversa lista"
    note "servicio OK en 127.0.0.1:$PORT"
    [ "$REVERT_DB_RESTORED" = 1 ] && note "la base de datos se restauró al respaldo previo a la actualización"
    exit 0
  fi
  echo "Tras revertir, el servicio NO responde. Revisa: journalctl -u centro -n 100 --no-pager" >&2
  exit 2
fi

# ── Actualizar ────────────────────────────────────────────────────────────────────────────────────────────────
say "Precondiciones"
[ -f "$INSTALL_SCRIPT" ] || die_pre "no encuentro $INSTALL_SCRIPT."
if [ "$DO_PULL" -eq 1 ]; then
  if [ -n "$(g status --porcelain --untracked-files=no)" ]; then
    die_pre "el repositorio $REPO_DIR tiene cambios sin confirmar (git status). Descártalos o usa --sin-pull."
  fi
  note "repositorio limpio"
fi

OLD_COMMIT="$(g rev-parse --short HEAD 2>/dev/null || echo desconocido)"
if [ "$DO_PULL" -eq 1 ]; then
  say "Trayendo cambios (git fetch + pull --ff-only)"
  g fetch --quiet origin || die_pre "git fetch falló (¿sin red o sin acceso al repositorio?)."
  g pull --ff-only --quiet || die_pre "git pull --ff-only falló: el repositorio de la VM divergió de origin (no se cambió nada)."
fi
NEW_COMMIT="$(g rev-parse --short HEAD 2>/dev/null || echo desconocido)"
note "commit instalado antes: $OLD_COMMIT"
note "commit a instalar:      $NEW_COMMIT"
if [ "$OLD_COMMIT" != "$NEW_COMMIT" ] && [ "$OLD_COMMIT" != desconocido ]; then
  g log --oneline "$OLD_COMMIT..$NEW_COMMIT" | sed 's/^/      /' | head -n 30
else
  note "sin commits nuevos (se vuelve a instalar igualmente: es idempotente)"
fi

# Con la puerta pública encendida, un install.sh sin PUBLIC_FUNNEL la apagaría: se conserva lo que ya hay.
if [ -z "${PUBLIC_FUNNEL+x}" ] && systemctl is-active --quiet centro-public 2>/dev/null; then
  export PUBLIC_FUNNEL=1
  note "la puerta pública está activa: se conserva (PUBLIC_FUNNEL=1). Para apagarla: sudo PUBLIC_FUNNEL=0 aeroacademy actualizar"
fi

HAVE_SNAPSHOT=0
BACKUP_FILE=""
MIG_BEFORE="$(mig_count)"
if [ -d "$APP_DIR" ] && [ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
  say "Instantánea del código instalado en $PREV_DIR"
  mkdir -p "$PREV_DIR"
  rsync -a --delete "${EXCLUDES[@]}" "$APP_DIR"/ "$PREV_DIR"/
  HAVE_SNAPSHOT=1
  if [ -f "$DB_PATH" ]; then
    say "Respaldo consistente de la base"
    umask 077   # lleva datos personales
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/pre-actualizar-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
    sqlite3 -cmd ".timeout 10000" "$DB_PATH" ".backup '$BACKUP_FILE'"
    [ -s "$BACKUP_FILE" ] || { echo "El respaldo quedó vacío: no se actualiza." >&2; exit 3; }
    note "$BACKUP_FILE"
    # Retención: las últimas $KEEP_BACKUPS (el nombre lleva la hora UTC, el orden alfabético es el cronológico).
    ls -1 "$BACKUP_DIR"/pre-actualizar-*.sqlite3 2>/dev/null | sort | head -n "-$KEEP_BACKUPS" | xargs -r rm -f || true
  else
    note "sin base de datos todavía: no hay nada que respaldar"
  fi
  {
    echo "commit_before=$OLD_COMMIT"
    echo "commit_after=$NEW_COMMIT"
    echo "db_backup=$BACKUP_FILE"
    echo "migrations_before=$MIG_BEFORE"
    echo "taken_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$INFO_FILE"
else
  note "primera instalación (no hay nada instalado): no habrá a qué volver si falla"
fi

say "Instalando ($INSTALL_SCRIPT)"
FAIL_REASON=""
if ! "$INSTALL_SCRIPT"; then
  FAIL_REASON="el instalador terminó con error"
else
  say "Comprobando que el servicio responde"
  if health_check; then
    note "servicio OK en 127.0.0.1:$PORT"
  else
    FAIL_REASON="el servicio no respondió tras instalar"
  fi
fi

if [ -z "$FAIL_REASON" ]; then
  MIG_AFTER="$(mig_count)"
  echo
  say "Actualización lista: $OLD_COMMIT -> $NEW_COMMIT"
  [ "$MIG_AFTER" != "$MIG_BEFORE" ] && note "migraciones aplicadas: $MIG_BEFORE -> $MIG_AFTER"
  [ -n "$BACKUP_FILE" ] && note "respaldo previo: $BACKUP_FILE (por si hace falta: sudo aeroacademy actualizar --revertir)"
  note "recarga el navegador con Ctrl+F5 para ver los estáticos nuevos"
  exit 0
fi

# ── Falla: reversa automática ─────────────────────────────────────────────────────────────────────────────────
echo
echo "############################################################" >&2
echo "# FALLÓ LA ACTUALIZACIÓN: $FAIL_REASON" >&2
echo "############################################################" >&2
if [ "$HAVE_SNAPSHOT" -ne 1 ]; then
  echo "No había versión anterior que restaurar (primera instalación). Revisa: journalctl -u centro -n 100 --no-pager" >&2
  exit 2
fi
REVERT_DB_RESTORED=0
if do_rollback yes; then
  repo_back_to "$OLD_COMMIT"
  echo
  echo "Resumen" >&2
  echo "  - Falló: $FAIL_REASON (commit $NEW_COMMIT)." >&2
  echo "  - Restaurado: código de $OLD_COMMIT; el servicio responde de nuevo en 127.0.0.1:$PORT." >&2
  if [ "$REVERT_DB_RESTORED" = 1 ]; then
    echo "  - BASE DE DATOS RESTAURADA desde $BACKUP_FILE: se perdió lo escrito entre el respaldo y la falla." >&2
  else
    echo "  - La base de datos no se tocó (no hubo migraciones nuevas)." >&2
  fi
  echo "  - No se revirtió: configuración de systemd/Tailscale que haya cambiado el instalador." >&2
  echo "  - Logs: journalctl -u centro -n 200 --no-pager" >&2
  exit 1
fi
echo "LA REVERSA TAMBIÉN FALLÓ: el servicio no responde. Intervención manual necesaria." >&2
echo "  - Código anterior: $PREV_DIR · respaldo de la base: ${BACKUP_FILE:-ninguno}" >&2
echo "  - Logs: journalctl -u centro -n 200 --no-pager" >&2
exit 2
