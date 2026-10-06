#!/usr/bin/env bash
# Controlla che il gestionale risponda e avvisa se è irraggiungibile.
#
# Da mettere in cron sul VPS ogni 5 minuti:
#   */5 * * * * cd /opt/gestionale && ./scripts/controllo_sito.sh >> /var/log/gestionale-controllo.log 2>&1
#
# L'avviso arriva solo dopo 3 controlli falliti di fila (per non allarmare per
# un singolo momento di rete), e un secondo avviso quando il sito torna su.
set -uo pipefail

URL="${URL:-https://aquaforma.space/accounts/login/}"
STATO_FILE="${STATO_FILE:-/var/tmp/gestionale-controllo.stato}"
ATTESE=3

cd "$(dirname "$0")/.."

codice=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$URL" || echo "000")
echo "$(date '+%F %H:%M')  risposta $codice"

avvisa() {
    docker compose exec -T web python manage.py avviso "$1" --oggetto "${2:-Avviso dal gestionale}" 2>&1 | tail -2 || true
}

if [ "$codice" = "200" ] || [ "$codice" = "302" ]; then
    if [ -f "$STATO_FILE" ]; then
        avvisa "Il gestionale è di nuovo raggiungibile (risposta $codice)." "Gestionale di nuovo attivo"
        rm -f "$STATO_FILE"
    fi
    exit 0
fi

# Conta i fallimenti consecutivi
fallimenti=1
if [ -f "$STATO_FILE" ]; then
    fallimenti=$(( $(cat "$STATO_FILE") + 1 ))
fi
echo "$fallimenti" > "$STATO_FILE"

if [ "$fallimenti" -eq "$ATTESE" ]; then
    avvisa "Il gestionale NON risponde (risposta $codice su $URL) da $ATTESE controlli di fila. Controlla il server." "Gestionale non raggiungibile"
fi

exit 0
