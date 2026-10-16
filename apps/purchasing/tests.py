"""Test dell'importazione dei listini fornitori."""
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.inventory.models import StockMovement
from apps.purchasing.models import PriceListItem, PurchaseOrder, SupplierPriceList

User = get_user_model()


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
        self.assertEqual(prodotto.min_stock, Decimal("0"), "l'import non imposta scorte minime")

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

    def test_reimport_riusa_articolo_con_codice_di_altro_fornitore(self):
        """Se il codice è di un altro fornitore si crea un articolo interno: al
        secondo import si deve riusare quello, senza creare doppioni."""
        from apps.core.models import UnitOfMeasure, VatRate

        pz = UnitOfMeasure.objects.get(code="PZ")
        iva = VatRate.objects.get(code="22")
        altro = Contact.objects.create(name="Altro fornitore", is_supplier=True)
        Product.objects.create(
            code="10303180", name="Articolo di un altro fornitore",
            uom=pz, sale_vat=iva, purchase_vat=iva, main_supplier=altro,
        )

        percorso = str(_file_axor())
        for _ in range(2):
            call_command("importa_listini", "axor", file=percorso, stdout=StringIO())

        self.assertEqual(Product.objects.count(), 3, "nessun articolo duplicato al secondo import")
        listino = SupplierPriceList.objects.get(name="AXOR 2027")
        self.assertEqual(listino.items.count(), 2)
        voce = listino.items.get(supplier_code="10303180")
        self.assertNotEqual(voce.product.code, "10303180")
        self.assertEqual(voce.product.main_supplier.name, "Hansgrohe srl")


class RicezioneConDdtFornitoreTest(TestCase):
    """Alla ricezione merce si può indicare il DDT del fornitore."""

    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        self.client.force_login(self.user)
        self.uom = UnitOfMeasure.objects.get(code="PZ")
        self.iva = VatRate.objects.get(code="22")
        self.fornitore = Contact.objects.create(name="Fornitore DDT S.p.A.", is_customer=False, is_supplier=True)
        self.articolo = Product.objects.create(
            name="Piatto doccia test",
            uom=self.uom,
            sale_price=Decimal("100.00"),
            sale_vat=self.iva,
            purchase_price=Decimal("50.00"),
            purchase_vat=self.iva,
        )
        self.ordine = PurchaseOrder.objects.create(
            supplier=self.fornitore, status=PurchaseOrder.STATUS_CONFIRMED
        )
        self.riga = self.ordine.lines.create(
            product=self.articolo, description="Riga", qty=Decimal("2"),
            uom=self.uom, unit_price=Decimal("50.00"), vat_rate=self.iva,
        )

    def test_pagina_ricezione_mostra_il_campo_ddt(self):
        pagina = self.client.get(
            reverse("purchasing:po_receive", args=[self.ordine.pk])
        ).content.decode("utf-8")
        self.assertIn('name="supplier_ddt"', pagina)

    def test_ricezione_salva_ddt_sullordine_e_nel_movimento(self):
        response = self.client.post(
            reverse("purchasing:po_receive", args=[self.ordine.pk]),
            {f"qty_{self.riga.pk}": "2", "supplier_ddt": "DDT 123/2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.ordine.refresh_from_db()
        self.assertEqual(self.ordine.supplier_ddt, "DDT 123/2026")
        self.assertEqual(self.ordine.status, PurchaseOrder.STATUS_RECEIVED)
        movimento = StockMovement.objects.get(reference=self.ordine.number)
        self.assertIn("DDT 123/2026", movimento.note)
        pagina = self.client.get(
            reverse("purchasing:po_detail", args=[self.ordine.pk])
        ).content.decode("utf-8")
        self.assertIn("DDT 123/2026", pagina)

    def test_stampa_ordine_fornitore_mostra_il_codice_articolo(self):
        pagina = self.client.get(
            reverse("purchasing:po_print", args=[self.ordine.pk])
        ).content.decode("utf-8")
        self.assertIn(self.articolo.code, pagina, "l'ordine fornitore mostra il codice articolo")


class StampaOrdineFornitoreTest(TestCase):
    """La stampa per il fornitore: niente sezioni; lordo, sconto e netto."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.fornitore = Contact.objects.create(name="Fornitore Stampa S.p.A.", is_customer=False, is_supplier=True)
        cls.articolo = Product.objects.create(
            name="Articolo stampa", uom=cls.uom, sale_price=Decimal("150"),
            sale_vat=cls.vat, purchase_price=Decimal("100"), purchase_vat=cls.vat,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.ordine = PurchaseOrder.objects.create(supplier=self.fornitore)
        self.ordine.lines.create(line_type="section", description="SEZIONE DA NASCONDERE")
        self.ordine.lines.create(
            product=self.articolo, description="Riga con sconto", qty=Decimal("1"),
            uom=self.uom, unit_price=Decimal("100.00"), discount_pct=Decimal("20"),
            vat_rate=self.vat,
        )
        self.ordine.recalculate()

    def _pagina(self):
        return self.client.get(
            reverse("purchasing:po_print", args=[self.ordine.pk])
        ).content.decode("utf-8")

    def test_niente_sezioni_nella_stampa(self):
        pagina = self._pagina()
        self.assertNotIn("SEZIONE DA NASCONDERE", pagina, "le sezioni non si stampano nell'ordine fornitore")

    def test_colonne_lordo_sconto_e_netto(self):
        pagina = self._pagina()
        self.assertIn("Netto", pagina, "deve esserci la colonna del prezzo netto")
        self.assertIn('<td class="num">100,00 €</td>', pagina, "il prezzo di listino (lordo)")
        self.assertIn('<td class="num">20%</td>', pagina, "lo sconto applicato")
        self.assertIn('<td class="num">80,00 €</td>', pagina, "il prezzo netto")


class ColonneModuliAcquistiTest(TestCase):
    """I moduli di acquisto non mostrano più la colonna Sezione."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")

    def setUp(self):
        self.client.force_login(self.user)

    def test_niente_colonna_sezione_in_ordine_e_fattura(self):
        for url in (reverse("purchasing:po_create"), reverse("billing:purchaseinvoice_create")):
            with self.subTest(url=url):
                pagina = self.client.get(url).content.decode("utf-8")
                self.assertNotIn(">Sezione<", pagina, "la colonna Sezione non deve comparire")
