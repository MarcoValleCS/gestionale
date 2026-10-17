"""Allinea le righe degli ordini fornitore in bozza al prezzo di listino.

Le righe create prima di questa correzione salvavano direttamente il prezzo
netto (quello di acquisto) con sconto 0. Il comando riporta il prezzo a quello
di vendita dell'articolo (il listino) e calcola lo sconto che mantiene lo
stesso netto: così l'ordine inviato al fornitore mostra listino e sconto.

Uso:

    python manage.py rinormalizza_prezzi_ordini_fornitore             # anteprima
    python manage.py rinormalizza_prezzi_ordini_fornitore --applica  # scrive
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import sconto_per_prezzo_acquisto

from ...models import PurchaseOrder


class Command(BaseCommand):
    help = "Riporta le righe degli ordini fornitore in bozza a prezzo di listino + sconto (netto invariato)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--applica",
            action="store_true",
            help="Scrive le modifiche (senza, mostra solo l'anteprima).",
        )

    def handle(self, *args, **opzioni):
        applica = opzioni["applica"]
        righe = 0
        ordini = 0
        for ordine in PurchaseOrder.objects.filter(status=PurchaseOrder.STATUS_DRAFT).order_by("pk"):
            cambiato = False
            for riga in ordine.lines.select_related("product"):
                prodotto = riga.product
                if prodotto is None or riga.discount_pct:
                    continue
                netto = riga.unit_price or Decimal("0")
                listino = prodotto.sale_price or Decimal("0")
                if netto <= 0 or listino <= netto:
                    continue
                sconto = sconto_per_prezzo_acquisto(listino, netto)
                if sconto <= 0:
                    continue
                self.stdout.write(
                    f"  {ordine.number}: {prodotto.code} — {netto} € → "
                    f"listino {listino} € con sconto {sconto}%"
                )
                if applica:
                    riga.unit_price = listino
                    riga.discount_pct = sconto
                    riga.save(update_fields=["unit_price", "discount_pct"])
                righe += 1
                cambiato = True
            if cambiato:
                ordini += 1
                if applica:
                    ordine.recalculate()
        if applica:
            self.stdout.write(self.style.SUCCESS(f"Aggiornati {ordini} ordini, {righe} righe."))
        else:
            self.stdout.write(
                f"Anteprima: {ordini} ordini e {righe} righe da aggiornare. "
                "Rilancia con --applica per scrivere."
            )
