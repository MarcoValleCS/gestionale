"""Invia un breve avviso via email.

Serve ai controlli automatici (backup, sito raggiungibile, spazio su disco): se
qualcosa non va, arriva una email invece di scoprirlo per caso.

Uso:
    python manage.py avviso "Il backup notturno è fallito" --oggetto "Backup fallito"
"""
from django.conf import settings
from django.core.mail import send_mail
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

        from django.core.mail import EmailMessage

        from apps.core.mailing import email_configured
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

        email = EmailMessage(
            subject=options["oggetto"],
            body=options["messaggio"],
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinatario],
        )

        allegato = options["allega"]
        if allegato:
            percorso = Path(allegato)
            if not percorso.is_file():
                self.stderr.write(f"Allegato non trovato: {allegato}. Avviso non inviato.")
                return
            email.attach(percorso.name, percorso.read_bytes(), "application/gzip")

        email.send(fail_silently=False)
        self.stdout.write(f"Avviso inviato a {destinatario}." + (f" Con allegato {Path(allegato).name}." if allegato else ""))
