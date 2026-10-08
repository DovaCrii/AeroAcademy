#!/usr/bin/env bash
# Diagnóstico de AeroAcademy en la VM: servicios, nodo Tailscale propio, certificado y respuesta. No cambia nada.
# Uso: sudo ./deploy/diagnostico.sh        (pega la salida completa cuando algo no responda)
set -uo pipefail
SOCK=/run/tailscale-aeroacademy/tailscaled.sock
TS=(tailscale --socket="$SOCK")
ENV_FILE=/etc/centro/env
HOST="$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | cut -d, -f1)"
PORT="${AEROACADEMY_PORT:-8010}"
say() { printf '\n== %s ==\n' "$1"; }

say "Servicios"
for u in centro tailscaled-aeroacademy aerocontrol; do printf '%-26s %s\n' "$u" "$(systemctl is-active "$u" 2>&1)"; done

say "La app responde en local (127.0.0.1:$PORT)"
curl -sS -m 5 -o /dev/null -w 'healthz con Host=%{url_effective} -> HTTP %{http_code}\n' -H "Host: $HOST" "http://127.0.0.1:$PORT/healthz" || echo "NO responde: revisa  journalctl -u centro -n 50"

say "Nodo Tailscale propio (estado)"
"${TS[@]}" status 2>&1 | head -15
echo "IPs del nodo: $("${TS[@]}" ip 2>&1 | tr '\n' ' ')"

say "Salud y avisos del nodo (aprobación pendiente, certificados, DNS…)"
"${TS[@]}" status --json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("BackendState:", d.get("BackendState"))
print("Health:", d.get("Health") or "sin avisos")
print("CertDomains:", d.get("CertDomains") or "(vacío: HTTPS Certificates no está activo para este nodo)")
print("Self.Online:", d.get("Self", {}).get("Online"), "| Self.DNSName:", d.get("Self", {}).get("DNSName"))
print("Self.Tags:", d.get("Self", {}).get("Tags") or "(sin etiquetas)")
' 2>&1

say "Lo que publica el nodo (serve)"
"${TS[@]}" serve status 2>&1 | head -10

say "Certificado HTTPS del nodo"
TMP="$(mktemp -d)"
if [ -n "$HOST" ] && "${TS[@]}" cert --cert-file "$TMP/c.crt" --key-file "$TMP/c.key" "$HOST" >"$TMP/out" 2>&1; then
  echo "OK: certificado emitido para $HOST"
else
  echo "FALLÓ:"; cat "$TMP/out" 2>/dev/null
fi
rm -rf "$TMP"

say "Prueba completa desde esta VM (HTTPS al nombre del nodo)"
curl -sS -m 15 -o /dev/null -w "https://$HOST/ -> HTTP %{http_code}\n" "https://$HOST/" 2>&1 | tail -2

say "Últimas líneas de los registros"
echo "-- tailscaled-aeroacademy"; journalctl -u tailscaled-aeroacademy -n 15 --no-pager 2>&1 | tail -15
echo "-- centro"; journalctl -u centro -n 8 --no-pager 2>&1 | tail -8

say "Pistas"
cat <<'EOF'
 · CertDomains vacío o «cert» falla  -> consola de Tailscale > DNS > activa «HTTPS Certificates».
 · BackendState distinto de Running o Health con «needs approval» -> consola > Machines > aprueba «aeroacademy».
 · Todo OK aquí pero el navegador falla -> política de acceso (ACL) de la tailnet: debe permitir a tu usuario llegar al equipo «aeroacademy» (puerto 443).
 · El nombre no resuelve en tu PC -> comprueba que MagicDNS esté activo y que tu equipo tenga Tailscale conectado.
EOF
