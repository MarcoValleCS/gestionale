"""Carica le pagine della guida del gestionale.

Le pagine scritte nel codice si creano se mancano. Di norma il comando aggiorna
anche le pagine del programma che non sono mai state modificate dall'interfaccia:
così, dopo un aggiornamento, la guida resta allineata senza perdere le
personalizzazioni fatte dall'amministratore. Con ``--aggiorna`` si sovrascrive
tutto, anche ciò che è stato modificato a mano.
"""
from django.core.management.base import BaseCommand


def _diversa(pagina, voce):
    """True se il contenuto della pagina differisce da quello del codice.

    Il corpo viene confrontato già ripulito: ``WikiPage.save()`` applica la
    stessa pulizia, quindi senza questo passaggio le pagine risulterebbero
    diverse a ogni avvio e verrebbero riscritte inutilmente.
    """
    from apps.core.richtext import clean_guida

    return (
        pagina.title != voce["title"]
        or pagina.area != voce["area"]
        or pagina.summary != voce.get("summary", "")
        or pagina.roles != voce.get("roles", "")
        or pagina.order != voce.get("order", 100)
        or pagina.body != clean_guida(voce["body"])
    )


class Command(BaseCommand):
    help = "Crea e aggiorna le pagine della guida (Impostazioni → Guida) senza toccare quelle modificate a mano."

    def add_arguments(self, parser):
        parser.add_argument("--aggiorna", action="store_true", help="Sovrascrive anche le pagine modificate dall'interfaccia.")
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
                # Una pagina modificata dall'interfaccia ha updated_by valorizzato:
                # non la si tocca, altrimenti si perdono le personalizzazioni.
                if pagina.updated_by_id is not None or not _diversa(pagina, voce):
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
                self.style.SUCCESS(
                    f"  guida: {creati} pagine create · {aggiornati} aggiornate · {invariati} lasciate com'erano"
                )
            )
