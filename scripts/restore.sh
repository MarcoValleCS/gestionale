#!/usr/bin/env bash
# Ripristino del database da un backup creato con scripts/backup.sh
#
# Uso:
#   ./scripts/restore.sh /opt/backups/gestionale/db_2026-10-01_0300.sql.gz
set -euo pipefail

FILE="${1:?Indica il file di backup .sql.gz da ripristinare}"
if [ ! -f "$FILE" ]; then
  echo "File non trovato: $FILE"
  exit 1
fi

cd "$(dirname "$0")/.."

DB_NAME="${DB_NAME:-gestionale}"
DB_USER="${DB_USER:-gestionale}"

echo "ATTENZIONE: il contenuto attuale del database verrà SOSTITUITO con $FILE."
read -r -p "Scrivi SI per continuare: " answer
if [ "$answer" != "SI" ]; then
  echo "Operazione annullata."
  exit 0
fi

# Prima di sovrascrivere si salva lo stato attuale: se il file di ripristino è
# sbagliato (o corrotto), si può tornare indietro.
SALVATAGGIO="$(dirname "$FILE")/pre-restore_$(date +%F_%H%M).sql.gz"
echo "→ Copia di sicurezza dello stato attuale in $SALVATAGGIO"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$SALVATAGGIO"

echo "→ Svuoto lo schema corrente…"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# ON_ERROR_STOP=1 fa fallire subito il ripristino al primo errore;
# --single-transaction lo rende atomico (o tutto, o niente).
echo "→ Ripristino i dati…"
gunzip -c "$FILE" | docker compose exec -T db psql -v ON_ERROR_STOP=1 --single-transaction -U "$DB_USER" -d "$DB_NAME"

echo "→ Riavvio l'applicazione…"
docker compose restart web

echo "Ripristino completato."
