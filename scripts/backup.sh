#!/usr/bin/env bash
# Backup del gestionale: database PostgreSQL + file caricati (logo, media).
#
# Uso:
#   ./scripts/backup.sh                        # salva in /opt/backups/gestionale
#   ./scripts/backup.sh /percorso/di/backup    # cartella personalizzata
#
# Da mettere in cron sul VPS, ad esempio ogni notte alle 3:00:
#   0 3 * * * cd /opt/gestionale && ./scripts/backup.sh >> /var/log/gestionale-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-/opt/backups/gestionale}}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%F_%H%M)"

cd "$(dirname "$0")/.."

DB_NAME="${DB_NAME:-gestionale}"
DB_USER="${DB_USER:-gestionale}"

mkdir -p "$BACKUP_DIR"

echo "→ Backup del database in $BACKUP_DIR/db_$STAMP.sql.gz"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz"

echo "→ Backup dei file caricati in $BACKUP_DIR/media_$STAMP.tar.gz"
docker compose exec -T web mkdir -p /app/media
docker compose exec -T web tar czf - -C /app media > "$BACKUP_DIR/media_$STAMP.tar.gz"

echo "→ Rimozione dei backup più vecchi di $RETENTION_DAYS giorni"
find "$BACKUP_DIR" -type f -name "*.gz" -mtime +"$RETENTION_DAYS" -delete

echo "→ Ultimi file presenti:"
ls -lh "$BACKUP_DIR" | tail -6
echo "Backup completato."
