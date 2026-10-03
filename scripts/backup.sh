#!/usr/bin/env bash
# Backup del gestionale: database PostgreSQL + file caricati (logo, media).
#
# Uso:
#   ./scripts/backup.sh                        # salva in /opt/backups/gestionale
#   ./scripts/backup.sh /percorso/di/backup    # cartella personalizzata
#
# Da mettere in cron sul VPS, ad esempio ogni notte alle 3:00:
#   0 3 * * * cd /opt/gestionale && ./scripts/backup.sh >> /var/log/gestionale-backup.log 2>&1
#
# Se qualcosa va storto arriva una email di avviso (vedi AVVISO_EMAIL nel .env).
# Con BACKUP_EMAIL impostato nel .env, la copia del database viene anche spedita
# per email: è la copia che resta fuori dal server.
set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-/opt/backups/gestionale}}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%F_%H%M)"

cd "$(dirname "$0")/.."

DB_NAME="${DB_NAME:-gestionale}"
DB_USER="${DB_USER:-gestionale}"

mkdir -p "$BACKUP_DIR"

avvisa() {
    # $1 = messaggio, $2 = oggetto
    docker compose exec -T web python manage.py avviso "$1" --oggetto "${2:-Avviso dal gestionale}" 2>&1 | tail -2 || true
}

# Se lo script esce con un errore, manda un avviso (una sola volta)
esito() {
    codice=$?
    if [ "$codice" -ne 0 ]; then
        echo "Backup fallito (codice $codice)."
        avvisa "Il backup notturno del gestionale è FALLITO (codice $codice). Controlla il server." "Backup fallito"
    fi
    exit "$codice"
}
trap esito EXIT

echo "→ Backup del database in $BACKUP_DIR/db_$STAMP.sql.gz"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz"

echo "→ Backup dei file caricati in $BACKUP_DIR/media_$STAMP.tar.gz"
docker compose exec -T web mkdir -p /app/media
docker compose exec -T web tar czf - -C /app media > "$BACKUP_DIR/media_$STAMP.tar.gz"

echo "→ Rimozione dei backup più vecchi di $RETENTION_DAYS giorni"
find "$BACKUP_DIR" -type f -name "*.gz" -mtime +"$RETENTION_DAYS" -delete

# Copia fuori dal server: il database (è piccolo) viene spedito per email.
# Si attiva mettendo BACKUP_EMAIL=indirizzo nel file .env del server.
if [ -n "${BACKUP_EMAIL:-}" ]; then
    echo "→ Invio della copia del database a $BACKUP_EMAIL"
    docker compose exec -T web python manage.py avviso \
        "Copia di sicurezza del database del $(date +%d/%m/%Y). Conservala: serve a ripristinare il gestionale in caso di guasto." \
        --oggetto "Backup gestionale $(date +%F)" \
        --a "$BACKUP_EMAIL" \
        --allega "/backups/db_$STAMP.sql.gz" 2>&1 | tail -2 || echo "  (invio non riuscito: la copia resta comunque sul server)"
fi

# Controllo dello spazio su disco: un disco pieno blocca tutto
USO_DISCO=$(df --output=pcent / | tail -1 | tr -dc '0-9')
echo "→ Disco usato: ${USO_DISCO}%"
if [ "${USO_DISCO:-0}" -ge 85 ]; then
    avvisa "Il disco del server è pieno al ${USO_DISCO}%. Libera spazio (vecchi backup, immagini Docker) per evitare blocchi." "Disco quasi pieno"
fi

echo "→ Ultimi file presenti:"
ls -lh "$BACKUP_DIR" | tail -6
echo "Backup completato."
