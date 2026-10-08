#!/usr/bin/env bash
# Respaldo en caliente de la base (notas, avance y casillas). Úsalo en cron diario.
set -euo pipefail
DEST=${1:-/var/backups/forma-ruta}
mkdir -p "$DEST"
sqlite3 /var/lib/forma-ruta/ruta.db ".backup '$DEST/ruta-$(date +%F).db'"
find "$DEST" -name 'ruta-*.db' -mtime +30 -delete
echo "Respaldo en $DEST"
