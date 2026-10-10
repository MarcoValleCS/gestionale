"""Spedisce le email accodate dalle pagine (coda in background).

Da mettere in cron sul server, per esempio ogni 2 minuti:

    */2 * * * * cd /opt/gestionale && flock -n /var/tmp/gestionale-coda-email.lock docker compose exec -T web python manage.py invia_coda_email >> /var/log/gestionale-coda-email.log 2>&1

Uso manuale:

    python manage.py invia_coda_email
    python manage.py invia_coda_email --limite 50
"""
import logging

from django.core.management.base import BaseCommand

from apps.core.mailing import invia_voce_coda
from apps.core.models import EmailInCoda

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Spedisce le email in attesa nella coda (accodate dalle pagine)."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=20, help="Quante email spedire per giro (default 20)")

    def handle(self, *args, **options):
        voci = list(
            EmailInCoda.objects.filter(stato=EmailInCoda.STATO_ATTESA).order_by("created_at", "pk")[: options["limite"]]
        )
        if not voci:
            self.stdout.write("Nessuna email in coda.")
            return
        inviate = 0
        for voce in voci:
            try:
                invia_voce_coda(voce)
            except Exception as exc:
                logger.warning("Coda email: invio a %s non riuscito (%s)", voce.to_email, exc)
                self.stdout.write(f"Non inviata a {voce.to_email}: {exc}")
            else:
                inviate += 1
        self.stdout.write(self.style.SUCCESS(f"Inviate {inviate} email su {len(voci)}."))
