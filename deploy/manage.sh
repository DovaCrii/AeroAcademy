#!/usr/bin/env bash
# Atajo para correr manage.py como el usuario `centro` con la configuración de producción.
# El instalador lo deja como /usr/local/bin/aeroacademy. Uso:  sudo aeroacademy aprobar   ·   sudo aeroacademy teo_probar
set -euo pipefail
cd /opt/aeroacademy
exec sudo -u centro bash -c 'set -a; . /etc/centro/env; set +a; exec .venv/bin/python manage.py "$@"' _ "$@"
