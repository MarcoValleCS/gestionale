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
# Un archivio rovinato si scopre prima di toccare il database, non a metà.
if ! gzip -t "$FILE"; then
  echo "Il file $FILE è corrotto: ripristino annullato."
  exit 1
fi
umask 077

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

# Durante il ripristino nessuno deve scrivere: si fermano gestionale e server
# MCP. All'uscita (anche in caso di errore) ripartono da soli.
MCP_ACCESO="$(docker compose --profile mcp ps --status running --quiet mcp 2>/dev/null || true)"
echo "→ Fermo l'applicazione…"
docker compose --profile mcp stop web mcp
riavvia() {
  echo "→ Riavvio l'applicazione…"
  docker compose up -d web
  # Il server MCP riparte solo se era acceso prima del ripristino.
  if [ -n "$MCP_ACCESO" ]; then
    docker compose --profile mcp up -d mcp
  fi
}
trap riavvia EXIT

# Lo svuotamento dello schema sta nella STESSA transazione del ripristino:
# se il file dà errore a metà, PostgreSQL annulla tutto e il database resta
# com'era (prima lo schema veniva svuotato a parte e un errore lo lasciava vuoto).
# ON_ERROR_STOP=1 si ferma al primo errore; --single-transaction: o tutto o niente.
echo "→ Ripristino i dati…"
{
  echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  gunzip -c "$FILE"
} | docker compose exec -T db psql -v ON_ERROR_STOP=1 --single-transaction -U "$DB_USER" -d "$DB_NAME"

echo "Ripristino completato."
