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
        parser.add_argument(
            "--forza",
            action="store_true",
            help="Applica lo sconto anche se i prezzi del listino sembrano già netti (sconto doppio).",
        )

    def handle(self, *args, **options):
        from apps.catalog.models import Product
        from apps.contacts.models import Contact
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

            from django.core.exceptions import ValidationError

            from apps.purchasing.models import SupplierPriceList
            from apps.purchasing.services import applica_sconto_listino, voci_gia_nette

            listini = SupplierPriceList.objects.filter(supplier=fornitore, is_active=True)
            for listino in listini:
                sospette, controllate = voci_gia_nette(listino, percentuale)
                if sospette:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {listino.name}: {len(sospette)} voci su {controllate} hanno già un prezzo "
                            f"vicino al netto (sconto già applicato?)"
                        )
                    )
                if options["dry_run"]:
                    self.stdout.write(f"  (prova) {listino.name}: sconto {percentuale}% su {listino.items.count()} voci")
                    continue
                try:
                    voci, aggiornati = applica_sconto_listino(listino, percentuale, forza=options["forza"])
                except ValidationError as errore:
                    raise CommandError("; ".join(errore.messages) + " (usa --forza solo se sei sicuro)") from errore
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  sconto {percentuale}% applicato a {voci} voci di {fornitore.name} ({listino.name}) · "
                        f"prezzi di acquisto aggiornati: {aggiornati}"
                    )
                )

        if not options["vendita"] and not options["sconto"]:
            self.stdout.write("  Indica --vendita oppure --sconto \"Fornitore\" PERCENTUALE.")
