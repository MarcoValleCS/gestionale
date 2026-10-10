"""Scarica le nuove email dalla casella aziendale.

Da mettere in cron sul server (un giro leggero ogni 20 minuti basta: la posta
si legge comunque dal database, e un giro troppo frequente ruba CPU al sito):

    */20 * * * * cd /opt/gestionale && flock -n /var/tmp/gestionale-posta.lock nice -n 10 docker compose exec -T web python manage.py sincronizza_posta --limite 40 >> /var/log/gestionale-posta.log 2>&1

Uso manuale:

    python manage.py sincronizza_posta
    python manage.py sincronizza_posta --limite 300
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.imap import PostaNonConfigurata, posta_configurata, sincronizza


class Command(BaseCommand):
    help = "Copia le email della casella aziendale nel gestionale (via IMAP)."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=40, help="Quante email recenti controllare (default 40)")
        parser.add_argument("--cartella", default="", help="Cartella IMAP (default: quella configurata)")
        parser.add_argument("--riclassifica", action="store_true", help="Ricalcola risposte/rilevanti sulle email già scaricate")

    def handle(self, *args, **options):
        if options["riclassifica"]:
            from apps.core.imap import riclassifica

            aggiornate = riclassifica()
            self.stdout.write(self.style.SUCCESS(f"Riclassificate {aggiornate} email."))
            return

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
