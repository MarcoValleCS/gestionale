"""Test dell'importazione dei listini fornitori."""
import tempfile
from io import StringIO
from pathlib import Path

import openpyxl
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.purchasing.models import PriceListItem, SupplierPriceList


def _file_axor(finiture=False):
    """Crea un file AXOR minimo con la stessa struttura dei listini veri.

    Riga 5 = intestazioni, dati dalla riga 6. Nel listino generale il prezzo è
    in colonna F, in quello finiture in colonna G.
    """
    libro = openpyxl.Workbook()
    foglio = libro.active
    foglio.append(["", "Hansgrohe S.r.l."])
    foglio.append([])
    foglio.append(["", "Listino elettronico AXOR 2027: inizio validità GENNAIO 2027"])
    foglio.append([])
    if finiture:
        foglio.append(["", "Codice", "Descrizione ITA", "Descrizione GER", "Brand", "codice EAN", "Prezzo 2027",
                       "Codice Gruppo", "Nome Gruppo", "Codice Classe", "Nome Classe", "Karton", "Pallet"])
        foglio.append(["", "10001140", "AXOR Starck - Miscelatore lavabo 100", "AXOR Starck Einhebel", "AX",
                       "4011097835556", 502.2, "EG017610", "Sanitary taps", "EC011328", "Washbasin mixing tap", 0, 0])
    else:
        foglio.append(["", "Codice", "Descrizione ITA", "Brand", "codice EAN", "Prezzo 2027", "Discount Group",
                       "Codice Gruppo", "Nome Gruppo", "Codice Classe", "Nome Classe", "Karton", "Pallet"])
        foglio.append(["", "10303180", "Corpo incasso", "AX", "4011097342597", 294.8, "3091",
                       "EG017610", "Sanitary taps", "EC011327", "Built-in mixing tap", 14, 162])
        # gruppo segnaposto: non deve creare una categoria
        foglio.append(["", "10823000", "Valvola d'arresto cucina", "AX", "4011097693712", 186.7, "3099",
                       "EG017610", "_missing", "", "", 0, 0])
    percorso = Path(tempfile.mkdtemp()) / ("finiture.xlsx" if finiture else "generale.xlsx")
    libro.save(percorso)
    libro.close()
    return percorso


class ImportaListiniAxorTest(TestCase):
    def test_importa_listino_generale(self):
        call_command(
            "importa_listini", "axor", file=str(_file_axor()), valido_dal="2027-01-01", stdout=StringIO()
        )

        listino = SupplierPriceList.objects.get(name="AXOR 2027")
        self.assertEqual(str(listino.valid_from), "2027-01-01")
        self.assertIsNone(listino.valid_to)
        self.assertEqual(listino.supplier.name, "Hansgrohe srl")

        prodotto = Product.objects.get(code="10303180")
        self.assertEqual(prodotto.name, "AXOR Corpo incasso")
        self.assertEqual(prodotto.barcode, "4011097342597")
        self.assertEqual(prodotto.category.name, "Rubinetteria")
        self.assertEqual(prodotto.main_supplier, listino.supplier)

        voce = PriceListItem.objects.get(pricelist=listino, product=prodotto)
        self.assertEqual(voce.supplier_code, "10303180")
        self.assertEqual(str(voce.price), "294.8000")

        # il gruppo «_missing» non deve creare una categoria
        segnaposto = Product.objects.get(code="10823000")
        self.assertIsNone(segnaposto.category)

    def test_importa_listino_finiture(self):
        call_command(
            "importa_listini", "axor-finiture", file=str(_file_axor(finiture=True)),
            valido_dal="2027-01-01", stdout=StringIO(),
        )

        listino = SupplierPriceList.objects.get(name="AXOR Finiture 2027")
        self.assertEqual(str(listino.valid_from), "2027-01-01")
        prodotto = Product.objects.get(code="10001140")
        self.assertEqual(prodotto.name, "AXOR Starck - Miscelatore lavabo 100")
        self.assertEqual(prodotto.barcode, "4011097835556")
        voce = PriceListItem.objects.get(pricelist=listino, product=prodotto)
        self.assertEqual(str(voce.price), "502.2000", "il prezzo delle finiture è nella colonna G")

    def test_reimportazione_non_duplica(self):
        percorso = str(_file_axor())
        for _ in range(2):
            call_command("importa_listini", "axor", file=percorso, stdout=StringIO())
        self.assertEqual(Product.objects.filter(code="10303180").count(), 1)
        self.assertEqual(SupplierPriceList.objects.filter(name="AXOR 2027").count(), 1)
        self.assertEqual(Contact.objects.filter(name="Hansgrohe srl").count(), 1)
        self.assertEqual(PriceListItem.objects.count(), 2)

    def test_data_non_valida(self):
        with self.assertRaises(CommandError):
            call_command("importa_listini", "axor", file=str(_file_axor()), valido_dal="01/01/2027", stdout=StringIO())
