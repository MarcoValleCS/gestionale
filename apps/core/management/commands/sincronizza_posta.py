"""Scarica le nuove email dalla casella aziendale.

Da mettere in cron sul server, per esempio ogni 5 minuti:

    */5 * * * * cd /opt/gestionale && docker compose exec -T web python manage.py sincronizza_posta >> /var/log/gestionale-posta.log 2>&1

Uso manuale:

    python manage.py sincronizza_posta
    python manage.py sincronizza_posta --limite 300
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.imap import PostaNonConfigurata, posta_configurata, sincronizza


class Command(BaseCommand):
    help = "Copia le email della casella aziendale nel gestionale (via IMAP)."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=100, help="Quante email recenti controllare (default 100)")
        parser.add_argument("--cartella", default="", help="Cartella IMAP (default: quella configurata)")

    def handle(self, *args, **options):
        if not posta_configurata():
            raise CommandError("Lettura della casella non configurata: imposta le variabili IMAP_* nel file .env.")

        try:
            esito = sincronizza(limite=options["limite"], cartella=options["cartella"] or None)
        except PostaNonConfigurata as exc:
            raise CommandError(str(exc))

        if esito["nuove"]:
            self.stdout.write(self.style.SUCCESS(f"Scaricate {esito['nuove']} nuove email ({esito['esaminate']} controllate)."))
        else:
            self.stdout.write(f"Nessuna email nuova ({esito['esaminate']} controllate).")
