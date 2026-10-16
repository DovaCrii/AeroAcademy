#!/usr/bin/env bash
# Atajo para correr manage.py como el usuario `centro` con la configuración de producción.
# El instalador lo deja como /usr/local/bin/aeroacademy. Uso:  sudo aeroacademy aprobar   ·   sudo aeroacademy teo_probar
# Palabras reservadas (no son comandos de manage.py):
#   sudo aeroacademy actualizar [--solo-comprobar|--sin-pull]   actualiza con reversa automática (deploy/actualizar.sh)
#   sudo aeroacademy revertir                                   vuelve a la versión anterior (actualizar.sh --revertir)
# `actualizar` se corre desde el repositorio (~/AeroAcademy) o, si no, desde el que registró el instalador en /etc/centro/repo.
set -euo pipefail

repo_script() {
  local dir
  for dir in "$PWD" "$(cat /etc/centro/repo 2>/dev/null || true)"; do
    if [ -n "$dir" ] && [ -x "$dir/deploy/actualizar.sh" ] && [ -d "$dir/.git" ]; then echo "$dir/deploy/actualizar.sh"; return 0; fi
  done
  echo "No encuentro el repositorio: entra a ~/AeroAcademy y repite." >&2
  return 1
}

case "${1:-}" in
  actualizar) shift; exec "$(repo_script)" "$@" ;;
  revertir) shift; exec "$(repo_script)" --revertir "$@" ;;
esac

cd /opt/aeroacademy
exec sudo -u centro bash -c 'set -a; . /etc/centro/env; set +a; exec .venv/bin/python manage.py "$@"' _ "$@"