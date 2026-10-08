#!/usr/bin/env bash
# Instala o actualiza Ruta Forma + Revit en la VM. Ejecutar con sudo desde la carpeta del proyecto.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/forma-ruta
PORT=8080

echo "==> Dependencias del sistema"
apt-get update -qq && apt-get install -y -qq python3 python3-venv rsync sqlite3 >/dev/null

echo "==> Usuario de servicio"
id forma >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin forma

echo "==> Copiando aplicación a $APP"
mkdir -p "$APP"
rsync -a --delete --exclude ".venv" --exclude "data" --exclude "__pycache__" "$SRC"/ "$APP"/

echo "==> Entorno Python"
[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
chown -R forma:forma "$APP"

echo "==> Servicio systemd"
install -m 644 "$APP/deploy/forma-ruta.service" /etc/systemd/system/forma-ruta.service
systemctl daemon-reload
systemctl enable --now forma-ruta
systemctl restart forma-ruta
sleep 2
curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null && echo "    servicio OK en 127.0.0.1:$PORT"

echo "==> Publicando en la tailnet con tailscale serve (HTTPS)"
if command -v tailscale >/dev/null; then
  tailscale serve --bg "$PORT" || echo "    Revisa que MagicDNS y HTTPS Certificates estén activos en la consola de Tailscale."
  tailscale serve status || true
else
  echo "    tailscale no está instalado en esta VM."
fi
echo "Listo."
