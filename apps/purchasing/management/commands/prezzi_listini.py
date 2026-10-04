"""Prezzi di vendita e di acquisto a partire dai listini fornitori.

Uso:
    python manage.py prezzi_listini --vendita
        Prezzo di vendita = prezzo di listino, per tutti gli articoli a listino.

    python manage.py prezzi_listini --sconto "Lacus srl" 55
        Imposta lo sconto fornitore su tutte le voci dei suoi listini e
        aggiorna il prezzo di acquisto (listino meno sconto).

Lo sconto si può impostare anche dal gestionale, nella pagina del listino.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Imposta i prezzi di vendita dai listini e applica lo sconto fornitore ai prezzi di acquisto."

    def add_arguments(self, parser):
        parser.add_argument("--vendita", action="store_true", help="Prezzo di vendita uguale al prezzo di listino.")
        parser.add_argument(
            "--sconto",
            nargs=2,
            metavar=("FORNITORE", "PERCENTUALE"),
            help="Sconto fornitore da applicare (es. --sconto \"Lacus srl\" 55).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Mostra il risultato senza salvare.")

    def handle(self, *args, **options):
        from apps.catalog.models import Product
        from apps.contacts.models import Contact
        from apps.core.rounding import round4
        from apps.purchasing.models import PriceListItem

        if options["vendita"]:
            voci = PriceListItem.objects.filter(pricelist__is_active=True).select_related("product")
            da_salvare = []
            for voce in voci:
                prodotto = voce.product
                if voce.price and prodotto.sale_price != voce.price:
                    prodotto.sale_price = voce.price
                    da_salvare.append(prodotto)
            if options["dry_run"]:
                self.stdout.write(f"  (prova) articoli da aggiornare: {len(da_salvare)}")
            else:
                Product.objects.bulk_update(da_salvare, ["sale_price"], batch_size=500)
                self.stdout.write(self.style.SUCCESS(f"  prezzi di vendita aggiornati: {len(da_salvare)}"))

        if options["sconto"]:
            nome, percentuale_testo = options["sconto"]
            fornitore = Contact.objects.filter(name__iexact=nome).first()
            if fornitore is None:
                raise CommandError(f"Fornitore non trovato: {nome}")
            try:
                percentuale = Decimal(str(percentuale_testo).replace(",", "."))
            except Exception as errore:
                raise CommandError(f"Percentuale non valida: {percentuale_testo} ({errore})") from errore
            if percentuale < 0 or percentuale > 100:
                raise CommandError("Lo sconto deve essere fra 0 e 100.")

            voci = PriceListItem.objects.filter(
                pricelist__supplier=fornitore, pricelist__is_active=True
            ).select_related("product")
            da_salvare = []
            for voce in voci:
                prodotto = voce.product
                prezzo_acquisto = round4(Decimal(voce.price or 0) * (1 - percentuale / 100))
                if prodotto.purchase_price != prezzo_acquisto:
                    prodotto.purchase_price = prezzo_acquisto
                    da_salvare.append(prodotto)
            if options["dry_run"]:
                self.stdout.write(f"  (prova) sconto {percentuale}% su {voci.count()} voci · articoli da aggiornare: {len(da_salvare)}")
            else:
                voci.update(discount_pct=percentuale)
                Product.objects.bulk_update(da_salvare, ["purchase_price"], batch_size=500)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  sconto {percentuale}% applicato a {voci.count()} voci di {fornitore.name} · "
                        f"prezzi di acquisto aggiornati: {len(da_salvare)}"
                    )
                )

        if not options["vendita"] and not options["sconto"]:
            self.stdout.write("  Indica --vendita oppure --sconto \"Fornitore\" PERCENTUALE.")
