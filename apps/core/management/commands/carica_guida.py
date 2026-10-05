"""Carica le pagine della guida del gestionale.

Le pagine scritte nel codice si creano se mancano. Con ``--aggiorna`` si
sovrascrive il testo anche delle pagine esistenti (per riportarle alla versione
del programma), mentre di norma le modifiche fatte dal gestionale restano.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea le pagine della guida (Impostazioni → Guida) senza toccare quelle modificate a mano."

    def add_arguments(self, parser):
        parser.add_argument("--aggiorna", action="store_true", help="Sovrascrive anche le pagine già presenti.")
        parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe fatto.")

    def handle(self, *args, **options):
        from apps.core.guida import PAGINE
        from apps.core.models import WikiPage

        creati = aggiornati = invariati = 0
        for voce in PAGINE:
            pagina = WikiPage.objects.filter(slug=voce["slug"]).first()
            if pagina is None:
                if not options["dry_run"]:
                    WikiPage.objects.create(
                        slug=voce["slug"],
                        title=voce["title"],
                        area=voce["area"],
                        summary=voce.get("summary", ""),
                        body=voce["body"],
                        roles=voce.get("roles", ""),
                        order=voce.get("order", 100),
                    )
                creati += 1
                continue

            if not options["aggiorna"]:
                invariati += 1
                continue

            pagina.title = voce["title"]
            pagina.area = voce["area"]
            pagina.summary = voce.get("summary", "")
            pagina.roles = voce.get("roles", "")
            pagina.order = voce.get("order", 100)
            pagina.body = voce["body"]
            if not options["dry_run"]:
                pagina.save()
            aggiornati += 1

        if options["dry_run"]:
            self.stdout.write(f"  (prova) da creare: {creati} · da aggiornare: {aggiornati} · invariati: {invariati}")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  guida: {creati} pagine create · {aggiornati} aggiornate · {invariati} lasciate com'erano")
            )
