"""Crea (se mancante) l'utente amministratore dalle variabili d'ambiente.

Usato all'avvio dei container: DJANGO_SUPERUSER_USERNAME / _PASSWORD / _EMAIL.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea l'utente amministratore iniziale dalle variabili d'ambiente (idempotente)."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not username or not password:
            self.stdout.write("Variabili DJANGO_SUPERUSER_USERNAME/PASSWORD non impostate: nessun utente creato.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Utente «{username}» già presente: nessuna azione.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Utente amministratore «{username}» creato."))
