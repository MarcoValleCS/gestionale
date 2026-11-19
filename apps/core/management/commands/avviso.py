"""Invia un breve avviso via email.

Serve ai controlli automatici (backup, sito raggiungibile, spazio su disco): se
qualcosa non va, arriva una email invece di scoprirlo per caso.

Uso:
    python manage.py avviso "Il backup notturno è fallito" --oggetto "Backup fallito"
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Manda un avviso via email all'indirizzo dell'azienda (o a quello indicato)."

    def add_arguments(self, parser):
        parser.add_argument("messaggio", help="Testo dell'avviso")
        parser.add_argument("--oggetto", default="Avviso dal gestionale")
        parser.add_argument("--a", dest="destinatario", default="", help="Indirizzo a cui mandare l'avviso")
        parser.add_argument("--allega", default="", help="Percorso di un file da allegare (es. la copia del database)")

    def handle(self, *args, **options):
        from pathlib import Path

        from apps.core.mailing import email_configured, invia_subito
        from apps.core.models import CompanySettings

        destinatario = options["destinatario"] or settings.AVVISO_EMAIL
        if not destinatario:
            azienda = CompanySettings.load()
            destinatario = azienda.email or ""
        if not destinatario:
            self.stderr.write("Nessun destinatario configurato: avviso non inviato.")
            return
        if not email_configured():
            self.stderr.write("Invio email non configurato: avviso non inviato.")
            return

        allegato = options["allega"]
        contenuto = None
        if allegato:
            percorso = Path(allegato)
            if not percorso.is_file():
                self.stderr.write(f"Allegato non trovato: {allegato}. Avviso non inviato.")
                return
            contenuto = percorso.read_bytes()

        # Dalla casella aziendale (Impostazioni › Email o file .env)
        invia_subito(
            to_email=destinatario,
            subject=options["oggetto"],
            message=options["messaggio"],
            attachment=contenuto,
            attachment_name=Path(allegato).name if allegato else "",
            attachment_type="application/gzip",
        )
        self.stdout.write(f"Avviso inviato a {destinatario}." + (f" Con allegato {Path(allegato).name}." if allegato else ""))
