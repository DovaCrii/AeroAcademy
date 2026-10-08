#!/usr/bin/env bash
# Respaldo diario: copia en caliente de la base (sqlite3 .backup) + los archivos privados (certificados y documentos).
# Retención: 30 días. Uso: backup.sh [carpeta-destino]
set -euo pipefail
DEST="${1:-/var/backups/centro}"
STATE=/var/lib/centro
STAMP="$(date +%F)"
mkdir -p "$DEST"
umask 077   # los respaldos contienen datos personales

# Con el servicio escribiendo, SQLite puede estar ocupado un instante: se espera hasta 10 s.
sqlite3 -cmd ".timeout 10000" "$STATE/db.sqlite3" ".backup '$DEST/db-$STAMP.sqlite3'"
# tar sale con 1 si un archivo cambió mientras se leía: no es un fallo del respaldo.
tar -C "$STATE" -czf "$DEST/media-$STAMP.tar.gz" media || [ $? -eq 1 ]

find "$DEST" -name 'db-*.sqlite3' -mtime +30 -delete
find "$DEST" -name 'media-*.tar.gz' -mtime +30 -delete
echo "Respaldo en $DEST ($STAMP)"
