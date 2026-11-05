#!/bin/sh
set -e

echo "Applico le migrazioni…"
python manage.py migrate --noinput

echo "Raccolgo i file statici…"
# Senza --clear: aggiorna solo i file cambiati (riavvii più veloci su VPS
# piccolo). I nomi con impronta rendono innocui gli eventuali file vecchi.
python manage.py collectstatic --noinput

echo "Creo l'utente amministratore se configurato…"
python manage.py create_admin

echo "Aggiorno le pagine della guida…"
# Aggiorna solo le pagine del programma non modificate dall'interfaccia: le
# personalizzazioni dell'amministratore restano intatte.
python manage.py carica_guida

echo "Avvio il server…"
exec "$@"
