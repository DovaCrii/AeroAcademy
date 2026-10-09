#!/usr/bin/env bash
# Instala o actualiza AeroAcademy en una VM Linux (Debian/Ubuntu). Idempotente: se puede correr de nuevo para actualizar.
# Uso: sudo ./deploy/install.sh
#
# Qué hace: usuario de sistema, código en /opt/aeroacademy, entorno con uv, /etc/centro/env, migraciones, semillas,
# estáticos, servicio systemd (gunicorn en 127.0.0.1:8010), tareas diarias (respaldo, vencimientos, seguimiento de Teo)
# y la publicación en la tailnet. NUNCA usa `tailscale funnel`.
#
# VM COMPARTIDA (p. ej. con AeroControl, que usa 127.0.0.1:8000 y los puertos HTTPS de `tailscale serve` con Funnel):
#   · gunicorn escucha en 127.0.0.1:8010 (AEROACADEMY_PORT);
#   · por defecto se publica con un NODO TAILSCALE PROPIO (otra instancia de tailscaled con su nombre, p. ej.
#     aeroacademy.<tu-tailnet>.ts.net): solo tailnet, sin Funnel, sin tocar nada de lo que ya sirva la VM;
#   · usuario, carpetas y servicios propios (`centro`, /opt/aeroacademy, /etc/centro, centro-*, tailscaled-aeroacademy).
#
# Configuración: si existe deploy/centro.env (copia de deploy/centro.env.plantilla con tus datos) manda siempre; se
# instala en /etc/centro/env (la anterior queda en env.bak) conservando la SECRET_KEY ya generada.
#
# Variables opcionales:
#   AEROACADEMY_PORT=8010            puerto local de gunicorn
#   AEROACADEMY_PUBLISH=node|serve|none   node (por defecto) = nodo propio; serve = un puerto HTTPS del nodo principal;
#                                    none = no publicar
#   AEROACADEMY_HOSTNAME=aeroacademy  nombre del nodo propio
#   AEROACADEMY_TS_AUTHKEY=tskey-…   clave de autenticación para dar de alta el nodo sin abrir un enlace
#   AEROACADEMY_TS_PORT=8443         (modo serve) puerto HTTPS del nodo principal
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/aeroacademy
USER_NAME=centro
ENV_DIR=/etc/centro
ENV_FILE="$ENV_DIR/env"
STATE=/var/lib/centro
PORT="${AEROACADEMY_PORT:-8010}"
PUBLISH="${AEROACADEMY_PUBLISH:-node}"
TS_HOSTNAME="${AEROACADEMY_HOSTNAME:-aeroacademy}"
TS_PORT="${AEROACADEMY_TS_PORT:-8443}"
NODE_SOCK=/run/tailscale-aeroacademy/tailscaled.sock

if [ "$(id -u)" -ne 0 ]; then echo "Ejecuta con sudo." >&2; exit 1; fi

set_env() {  # set_env CLAVE valor: reemplaza la línea o la agrega al final
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
new_secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(64))'; }

echo "==> Dependencias del sistema"
apt-get update -qq
apt-get install -y -qq python3 rsync sqlite3 curl ca-certificates >/dev/null

echo "==> uv"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh >/dev/null
fi

echo "==> Comprobando que el puerto $PORT es nuestro o está libre"
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q . && ! systemctl is-active --quiet centro.service; then
  echo "El puerto $PORT ya lo usa otro servicio. Elige otro: AEROACADEMY_PORT=8011 sudo -E ./deploy/install.sh" >&2
  exit 1
fi

echo "==> Usuario de servicio y carpetas"
id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$APP" "$ENV_DIR" "$STATE/media" /var/backups/centro
chown "$USER_NAME:$USER_NAME" "$STATE" "$STATE/media" /var/backups/centro

echo "==> Copiando la aplicación a $APP"
rsync -a --delete \
  --exclude ".venv" --exclude ".uv-python" --exclude ".gunicorn" --exclude "__pycache__" --exclude ".git" --exclude "staticfiles" \
  --exclude "db.sqlite3*" --exclude "media" --exclude ".env" --exclude "deploy/centro.env" --exclude "private" \
  "$SRC"/ "$APP"/

echo "==> Configuración en $ENV_FILE"
umask 077   # el archivo nace sin permisos para otros: lleva la SECRET_KEY y la clave de Teo
OLD_SECRET=""
if [ -f "$ENV_FILE" ]; then OLD_SECRET="$(grep '^SECRET_KEY=' "$ENV_FILE" | cut -d= -f2- || true)"; fi
if [ -f "$SRC/deploy/centro.env" ]; then
  if [ -f "$ENV_FILE" ]; then cp "$ENV_FILE" "$ENV_FILE.bak"; fi
  cp "$SRC/deploy/centro.env" "$ENV_FILE"
  if grep -q '^SECRET_KEY=$' "$ENV_FILE"; then set_env SECRET_KEY "${OLD_SECRET:-$(new_secret)}"; fi
  echo "    instalada desde deploy/centro.env"
elif [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOF
# Configuración de AeroAcademy. Nunca se versiona. Reinicia el servicio después de editarla.
# Mejor: copia deploy/centro.env.plantilla como deploy/centro.env, complétala y vuelve a correr el instalador.
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=$(new_secret)
ALLOWED_HOSTS=
PUBLIC_HTTPS_PORT=443
DATABASE_PATH=$STATE/db.sqlite3
MEDIA_ROOT=$STATE/media
STATIC_ROOT=$APP/staticfiles
TRUSTED_PROXY_IPS=127.0.0.1,::1
BOOTSTRAP_ADMINS=
NIM_API_KEY=
BOT_ENABLED=true
BOT_DAILY_LIMIT=40
EOF
  echo "    creada vacía: complétala (o usa deploy/centro.env) y vuelve a correr este script"
else
  echo "    ya existe; no se toca"
fi
chmod 640 "$ENV_FILE"; chown root:"$USER_NAME" "$ENV_FILE"

if [ "$PUBLISH" != "node" ] && grep -q '^ALLOWED_HOSTS=$' "$ENV_FILE"; then
  echo "ALLOWED_HOSTS está vacío en $ENV_FILE: complétalo y vuelve a ejecutar." >&2
  exit 1
fi

echo "==> Contenido DGAC (privado, fuera de git)"
# Material interno de JEJ: se copia aparte desde tu computador a ~/AeroAcademy/private/dgac (como centro.env).
if [ -d "$SRC/private/dgac" ]; then
  mkdir -p "$STATE/dgac"
  rsync -a --delete "$SRC/private/dgac"/ "$STATE/dgac"/
  chown -R "$USER_NAME:$USER_NAME" "$STATE/dgac"
  chmod -R go-rwx "$STATE/dgac"
  echo "    instalado en $STATE/dgac"
else
  echo "    sin private/dgac: la sección DGAC dirá que falta el contenido (se puede copiar después)"
fi
set_env DGAC_DATA_DIR "$STATE/dgac"

echo "==> Entorno Python (uv)"
cd "$APP"
# Python 3.12 lo instala uv dentro de /opt/aeroacademy (no en /root): así el usuario `centro` puede leerlo.
export UV_PYTHON_INSTALL_DIR="$APP/.uv-python"
# Siempre Python 3.12 (el probado), aunque el del sistema sea más nuevo (Ubuntu 26.04 trae 3.14).
export UV_PYTHON=3.12
UV_PROJECT_ENVIRONMENT="$APP/.venv" uv sync --frozen --no-dev
mkdir -p "$APP/.gunicorn"   # gunicorn 26 guarda aquí su socket de control (el resto de /opt queda de solo lectura)
chown -R "$USER_NAME:$USER_NAME" "$APP"

run_manage() {
  sudo -u "$USER_NAME" bash -c 'set -a; . "$1"; set +a; shift; exec "$@"' _ "$ENV_FILE" "$APP/.venv/bin/python" manage.py "$@"
}

# ── Nodo Tailscale propio ────────────────────────────────────────────────────────────────────────────────────────
HC_HOST="$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d= -f2 | cut -d, -f1)"
TS=()
if [ "$PUBLISH" = "node" ]; then
  echo "==> Nodo Tailscale propio ($TS_HOSTNAME)"
  command -v tailscaled >/dev/null || { echo "tailscale no está instalado en esta VM." >&2; exit 1; }
  install -m 644 "$APP/deploy/tailscaled-aeroacademy.service" /etc/systemd/system/tailscaled-aeroacademy.service
  systemctl daemon-reload
  systemctl enable tailscaled-aeroacademy.service
  systemctl restart tailscaled-aeroacademy.service   # aplica cambios de la unidad (p. ej. --statedir)
  TS=(tailscale --socket="$NODE_SOCK")
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S "$NODE_SOCK" ] && break; sleep 1; done
  # BackendState «Running» = el nodo ya está dado de alta (el texto de `status` cambia entre versiones).
  # Recién reiniciado pasa unos segundos por NoState/Starting: se espera a un estado definitivo.
  BACKEND=""
  for _ in $(seq 1 20); do
    BACKEND="$("${TS[@]}" status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' 2>/dev/null || true)"
    case "$BACKEND" in Running|NeedsLogin|NeedsMachineAuth|Stopped) break ;; esac
    sleep 1
  done
  if [ "$BACKEND" != "Running" ]; then
    echo "    Hay que dar de alta el nodo en tu tailnet (una sola vez)."
    if [ -n "${AEROACADEMY_TS_AUTHKEY:-}" ]; then
      "${TS[@]}" up --hostname="$TS_HOSTNAME" --auth-key="$AEROACADEMY_TS_AUTHKEY"
    else
      echo "    Abre el enlace que aparece abajo e inicia sesión con tu cuenta de Tailscale:"
      timeout 600 "${TS[@]}" up --hostname="$TS_HOSTNAME" || { echo "No se completó el inicio de sesión: vuelve a correr el instalador." >&2; exit 1; }
    fi
  fi
  DNSNAME="$("${TS[@]}" status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
  echo "    nodo en la tailnet: $DNSNAME"
  set_env ALLOWED_HOSTS "$DNSNAME"
  set_env PUBLIC_HTTPS_PORT 443
  HC_HOST="$DNSNAME"
fi

echo "==> Estáticos, migraciones y semillas"
run_manage collectstatic --noinput >/dev/null
run_manage migrate --noinput
run_manage seed_catalog
run_manage cargar_dgac || true   # ruta DGAC desde $STATE/dgac (si está)
run_manage puesta_en_marcha || true   # hilo de bienvenida (una vez) y lista de lo que falta
run_manage reindex_assistant || true

echo "==> Servicios systemd"
install -m 644 deploy/centro.service /etc/systemd/system/centro.service
sed -i "s|127.0.0.1:8010|127.0.0.1:$PORT|" /etc/systemd/system/centro.service
for unit in centro-backup.service centro-backup.timer centro-expiry.service centro-expiry.timer centro-teo.service centro-teo.timer centro-alerta@.service; do
  install -m 644 "deploy/$unit" "/etc/systemd/system/$unit"
done
chmod 755 "$APP/deploy/backup.sh" "$APP/deploy/manage.sh"   # rsync ya los copió: aquí solo se les da permiso de ejecución
ln -sf "$APP/deploy/manage.sh" /usr/local/bin/aeroacademy   # atajo: sudo aeroacademy <comando>  (aprobar, teo_probar…)
systemctl daemon-reload
systemctl enable --now centro.service centro-backup.timer centro-expiry.timer centro-teo.timer
systemctl restart centro.service

echo "==> Comprobando el servicio"
# Django rechaza un Host que no esté en ALLOWED_HOSTS: se usa el primero (el nombre MagicDNS).
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -H "Host: $HC_HOST" "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then OK=1; break; fi
  sleep 1
done
[ "${OK:-0}" = 1 ] && echo "    servicio OK en 127.0.0.1:$PORT" || { echo "    el servicio no responde; revisa: journalctl -u centro" >&2; exit 1; }

echo "==> Publicando en la tailnet (solo tailnet; nunca Funnel)"
case "$PUBLISH" in
  node)
    "${TS[@]}" serve --bg --https=443 "http://127.0.0.1:$PORT"
    "${TS[@]}" serve status || true
    # El certificado se pide ahora y no en la primera visita: si falla, el navegador solo ve «conexión cerrada».
    echo "==> Certificado HTTPS del nodo"
    CERT_TMP="$(mktemp -d)"
    if "${TS[@]}" cert --cert-file "$CERT_TMP/c.crt" --key-file "$CERT_TMP/c.key" "$HC_HOST" >"$CERT_TMP/out" 2>&1; then
      echo "    certificado listo para $HC_HOST"
    else
      echo "    No se pudo emitir el certificado de $HC_HOST:" >&2
      sed 's/^/      /' "$CERT_TMP/out" >&2
      echo "    Revisa en la consola de Tailscale: DNS > HTTPS Certificates activado, y Machines > «aeroacademy» aprobada." >&2
      echo "    Luego corre de nuevo el instalador, o  sudo ./deploy/diagnostico.sh  para ver el detalle." >&2
      rm -rf "$CERT_TMP"
      exit 1
    fi
    rm -rf "$CERT_TMP"
    echo "    Dirección: https://$HC_HOST"
    ;;
  serve)
    CURRENT="$(tailscale serve status 2>/dev/null || true)"
    if echo "$CURRENT" | grep -q ":$TS_PORT" && ! echo "$CURRENT" | grep -q "127.0.0.1:$PORT"; then
      echo "    El puerto HTTPS $TS_PORT de la tailnet ya sirve otra cosa: no se toca. Usa AEROACADEMY_PUBLISH=node (nodo propio)." >&2
      exit 1
    fi
    tailscale serve --bg --https="$TS_PORT" "http://127.0.0.1:$PORT"
    echo "    Dirección: https://$HC_HOST:$TS_PORT"
    ;;
  none) echo "    sin publicar (AEROACADEMY_PUBLISH=none)";;
  *) echo "AEROACADEMY_PUBLISH debe ser node, serve o none." >&2; exit 1;;
esac
echo "Listo. No uses 'tailscale funnel': el sitio es solo para la tailnet."
