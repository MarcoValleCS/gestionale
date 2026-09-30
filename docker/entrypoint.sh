#!/bin/sh
set -e

echo "Applico le migrazioni…"
python manage.py migrate --noinput

echo "Raccolgo i file statici…"
python manage.py collectstatic --noinput --clear

echo "Creo l'utente amministratore se configurato…"
python manage.py create_admin

echo "Avvio il server…"
exec "$@"
