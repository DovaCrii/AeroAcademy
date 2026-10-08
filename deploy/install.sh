#!/usr/bin/env bash
# Instala o actualiza AeroAcademy en una VM Linux (Debian/Ubuntu). Idempotente: se puede correr de nuevo para actualizar.
# Uso: sudo ./deploy/install.sh [nombre-magicdns.tailnet.ts.net]
#
# Qué hace: usuario de sistema, código en /opt/aeroacademy, entorno con uv, /etc/centro/env (solo la primera vez),
# migraciones, semillas, archivos estáticos, servicio systemd (gunicorn en 127.0.0.1:8000), tareas diarias
# (respaldo y vencimientos) y publicación en la tailnet con `tailscale serve`. NUNCA usa `tailscale funnel`.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/aeroacademy
USER_NAME=centro
ENV_DIR=/etc/centro
ENV_FILE="$ENV_DIR/env"
STATE=/var/lib/centro
PORT=8000
HOST="${1:-}"

if [ "$(id -u)" -ne 0 ]; then echo "Ejecuta con sudo." >&2; exit 1; fi

echo "==> Dependencias del sistema"
apt-get update -qq
apt-get install -y -qq python3 python3-venv rsync sqlite3 curl ca-certificates >/dev/null

echo "==> uv"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh >/dev/null
fi

echo "==> Usuario de servicio y carpetas"
id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$APP" "$ENV_DIR" "$STATE/media" /var/backups/centro
chown "$USER_NAME:$USER_NAME" "$STATE" "$STATE/media" /var/backups/centro

echo "==> Copiando la aplicación a $APP"
rsync -a --delete \
  --exclude ".venv" --exclude "__pycache__" --exclude ".git" --exclude "staticfiles" \
  --exclude "db.sqlite3*" --exclude "media" --exclude ".env" --exclude "deploy/centro.env" \
  "$SRC"/ "$APP"/

echo "==> Configuración en $ENV_FILE"
if [ ! -f "$ENV_FILE" ] && [ -f "$SRC/deploy/centro.env" ]; then
  # La persona dejó su configuración lista (copia de deploy/centro.env.plantilla con la clave y el correo).
  umask 077
  cp "$SRC/deploy/centro.env" "$ENV_FILE"
  if grep -q '^SECRET_KEY=$' "$ENV_FILE"; then
    sed -i "s|^SECRET_KEY=\$|SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')|" "$ENV_FILE"
  fi
  if [ -n "$HOST" ] && grep -q '^ALLOWED_HOSTS=$' "$ENV_FILE"; then
    sed -i "s|^ALLOWED_HOSTS=\$|ALLOWED_HOSTS=$HOST|" "$ENV_FILE"
  fi
  chmod 640 "$ENV_FILE"; chown root:"$USER_NAME" "$ENV_FILE"
  echo "    creado desde deploy/centro.env"
elif [ ! -f "$ENV_FILE" ]; then
  umask 077   # el archivo nace sin permisos para otros: lleva la SECRET_KEY
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
  cat > "$ENV_FILE" <<EOF
# Configuración de AeroAcademy. Nunca se versiona. Reinicia el servicio después de editarla.
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=$SECRET
ALLOWED_HOSTS=${HOST}
DATABASE_PATH=$STATE/db.sqlite3
MEDIA_ROOT=$STATE/media
STATIC_ROOT=$APP/staticfiles
TRUSTED_PROXY_IPS=127.0.0.1,::1
# Quién queda como administrador la primera vez (correo de Tailscale, separados por coma):
BOOTSTRAP_ADMINS=
# Teo (opcional): la clave se crea en https://build.nvidia.com
NIM_API_KEY=
BOT_ENABLED=true
BOT_DAILY_LIMIT=40
EOF
  chmod 640 "$ENV_FILE"
  chown root:"$USER_NAME" "$ENV_FILE"
  echo "    creado. Completa ALLOWED_HOSTS y BOOTSTRAP_ADMINS, y vuelve a correr este script."
  if [ -z "$HOST" ]; then echo "    (falta el nombre MagicDNS: ./deploy/install.sh mi-vm.tailnet.ts.net)"; fi
else
  echo "    ya existe; no se toca"
  if [ -n "$HOST" ] && grep -q '^ALLOWED_HOSTS=$' "$ENV_FILE"; then
    sed -i "s|^ALLOWED_HOSTS=\$|ALLOWED_HOSTS=$HOST|" "$ENV_FILE"
    echo "    ALLOWED_HOSTS completado con $HOST"
  fi
fi

if grep -q '^ALLOWED_HOSTS=$' "$ENV_FILE"; then
  echo "ALLOWED_HOSTS está vacío en $ENV_FILE: complétalo y vuelve a ejecutar." >&2
  exit 1
fi

echo "==> Entorno Python (uv)"
cd "$APP"
UV_PROJECT_ENVIRONMENT="$APP/.venv" uv sync --frozen --no-dev
chown -R "$USER_NAME:$USER_NAME" "$APP"

run_manage() {
  sudo -u "$USER_NAME" bash -c 'set -a; . "$1"; set +a; shift; exec "$@"' _ "$ENV_FILE" "$APP/.venv/bin/python" manage.py "$@"
}

echo "==> Estáticos, migraciones y semillas"
run_manage collectstatic --noinput >/dev/null
run_manage migrate --noinput
run_manage seed_catalog
run_manage reindex_assistant || true

echo "==> Servicios systemd"
install -m 644 deploy/centro.service /etc/systemd/system/centro.service
install -m 644 deploy/centro-backup.service /etc/systemd/system/centro-backup.service
install -m 644 deploy/centro-backup.timer /etc/systemd/system/centro-backup.timer
install -m 644 deploy/centro-expiry.service /etc/systemd/system/centro-expiry.service
install -m 644 deploy/centro-expiry.timer /etc/systemd/system/centro-expiry.timer
install -m 644 deploy/centro-teo.service /etc/systemd/system/centro-teo.service
install -m 644 deploy/centro-teo.timer /etc/systemd/system/centro-teo.timer
install -m 755 deploy/backup.sh "$APP/deploy/backup.sh"
systemctl daemon-reload
systemctl enable --now centro.service centro-backup.timer centro-expiry.timer centro-teo.timer
systemctl restart centro.service

echo "==> Comprobando el servicio"
# Django rechaza un Host que no esté en ALLOWED_HOSTS: se usa el primero (el nombre MagicDNS).
HC_HOST="$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d= -f2 | cut -d, -f1)"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -H "Host: $HC_HOST" "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then OK=1; break; fi
  sleep 1
done
[ "${OK:-0}" = 1 ] && echo "    servicio OK en 127.0.0.1:$PORT" || { echo "    el servicio no responde; revisa: journalctl -u centro" >&2; exit 1; }

echo "==> Publicando en la tailnet (tailscale serve, solo HTTPS interno)"
if command -v tailscale >/dev/null; then
  tailscale serve --bg "$PORT" || echo "    Revisa que MagicDNS y HTTPS Certificates estén activos en la consola de Tailscale."
  tailscale serve status || true
else
  echo "    tailscale no está instalado en esta VM."
fi
echo "Listo. No uses 'tailscale funnel': el sitio es solo para la tailnet."
