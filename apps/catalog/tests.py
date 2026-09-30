"""Test di importazione articoli e creazione rapida."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.purchasing.models import PriceListItem, SupplierPriceList

from . import importer
from .models import Product

User = get_user_model()

CSV_SAMPLE = """descrizione;codice;categoria;unita_misura;prezzo_vendita;iva_vendita;prezzo_acquisto;iva_acquisto;scorta_minima;fornitore;etichette
Bullone M10;ARTX1;Ricambi;PZ;0,50;22;0,25;22;100;Ferramenta Test;Promozione
Montaggio in cantiere;;Servizi;H;45,00;22;0;22;0;;
"""


class ImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.supplier = Contact.objects.create(name="Ferramenta Test", is_customer=False, is_supplier=True)

    def login(self):
        self.client.force_login(self.user)

    def upload(self, content, name="articoli.csv"):
        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")

    # ------------------------------------------------------------- parsing
    def test_read_table_csv(self):
        rows = importer.read_table(self.upload(CSV_SAMPLE))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Bullone M10")
        self.assertEqual(rows[0]["code"], "ARTX1")
        self.assertEqual(rows[0]["sale_price"], "0,50")

    def test_read_table_senza_descrizione(self):
        with self.assertRaises(ValueError):
            importer.read_table(self.upload("codice;prezzo\nA1;5\n"))

    def test_read_table_excel(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["descrizione", "prezzo_vendita", "unita_misura"])
        sheet.append(["Articolo da Excel", 12.5, "PZ"])
        buffer = BytesIO()
        workbook.save(buffer)

        file_obj = SimpleUploadedFile(
            "articoli.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        rows = importer.read_table(file_obj)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Articolo da Excel")
        self.assertEqual(rows[0]["sale_price"], "12.5")

    # ------------------------------------------------------------ import
    def test_import_crea_articoli(self):
        rows = importer.read_table(self.upload(CSV_SAMPLE))
        report = importer.import_products(rows, user=self.user)

        self.assertEqual(report.created, 2)
        self.assertEqual(report.updated, 0)
        self.assertEqual(report.errors, [])

        bullone = Product.objects.get(name="Bullone M10")
        self.assertEqual(bullone.code, "ARTX1")
        self.assertEqual(bullone.sale_price, Decimal("0.50"))
        self.assertEqual(bullone.purchase_price, Decimal("0.25"))
        self.assertEqual(bullone.min_stock, Decimal("100"))
        self.assertEqual(bullone.main_supplier.name, "Ferramenta Test")
        self.assertEqual(bullone.category.name, "Ricambi")
        self.assertTrue(bullone.tags.filter(name="Promozione").exists())

        montaggio = Product.objects.get(name="Montaggio in cantiere")
        self.assertEqual(montaggio.uom.code, "H")
        self.assertEqual(montaggio.category.name, "Servizi")

    def test_import_aggiorna_esistente_per_codice(self):
        existing = Product.objects.create(
            code="ARTX1",
            name="Nome vecchio",
            uom=UnitOfMeasure.objects.get(code="PZ"),
            sale_price=Decimal("1.00"),
            sale_vat=VatRate.objects.get(code="22"),
            purchase_price=Decimal("1.00"),
            purchase_vat=VatRate.objects.get(code="22"),
        )
        rows = importer.read_table(self.upload(CSV_SAMPLE))
        report = importer.import_products(rows, user=self.user)

        self.assertEqual(report.created, 1)  # solo Montaggio
        self.assertEqual(report.updated, 1)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Bullone M10")
        self.assertEqual(existing.sale_price, Decimal("0.50"))

    def test_import_aggiorna_listino_fornitore(self):
        rows = importer.read_table(self.upload(CSV_SAMPLE))
        report = importer.import_products(rows, update_pricelist=True, user=self.user)

        self.assertEqual(report.price_items, 1)  # solo il bullone ha prezzo di acquisto
        bullone = Product.objects.get(name="Bullone M10")
        pricelist = SupplierPriceList.objects.get(supplier=bullone.main_supplier)
        item = PriceListItem.objects.get(pricelist=pricelist, product=bullone)
        self.assertEqual(item.price, Decimal("0.25"))

    def test_import_riga_senza_descrizione_segnata(self):
        rows = [{"sale_price": "1"}]
        report = importer.import_products(rows, user=self.user)
        self.assertEqual(report.created, 0)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("Descrizione mancante", report.errors[0][1])

    def test_import_fornitore_predefinito(self):
        rows = [{"name": "Articolo senza fornitore", "sale_price": "5"}]
        report = importer.import_products(rows, default_supplier=self.supplier, user=self.user)
        self.assertEqual(report.created, 1)
        product = Product.objects.get(name="Articolo senza fornitore")
        self.assertEqual(product.main_supplier, self.supplier)

    # ------------------------------------------------------ vista e modello
    def test_pagina_import_e_modello_csv(self):
        self.login()
        response = self.client.get(reverse("catalog:product_import"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formato del file")

        response = self.client.get(reverse("catalog:product_import_template"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("descrizione", response.content.decode("utf-8"))

    def test_import_dalla_vista(self):
        self.login()
        response = self.client.post(
            reverse("catalog:product_import"),
            {"file": self.upload(CSV_SAMPLE), "supplier": "", "update_pricelist": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importazione completata")
        self.assertEqual(Product.objects.count(), 2)


class QuickCreateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")

    def setUp(self):
        self.client.force_login(self.user)

    def test_crea_rapida_articolo(self):
        response = self.client.post(
            reverse("catalog:quick_create"),
            {
                "name": "Articolo al volo",
                "uom": self.uom.pk,
                "sale_price": "7.50",
                "sale_vat": self.vat.pk,
                "purchase_price": "4",
                "purchase_vat": self.vat.pk,
                "context": "sale",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("id", payload)
        self.assertIn("Articolo al volo", payload["label"])
        product = Product.objects.get(pk=payload["id"])
        self.assertEqual(product.sale_price, Decimal("7.50"))
        self.assertTrue(product.code.startswith("ART"))

    def test_crea_rapida_articolo_senza_nome(self):
        response = self.client.post(reverse("catalog:quick_create"), {"uom": self.uom.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])

    def test_crea_rapido_cliente(self):
        response = self.client.post(
            reverse("contacts:quick_create"),
            {"name": "Cliente Immediato S.r.l.", "kind": "customer", "city": "Bologna"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        contact = Contact.objects.get(pk=payload["id"])
        self.assertTrue(contact.is_customer)
        self.assertFalse(contact.is_supplier)
        self.assertIn(contact.code, payload["label"])

    def test_crea_rapido_fornitore(self):
        response = self.client.post(
            reverse("contacts:quick_create"),
            {"name": "Fornitore Immediato", "kind": "supplier"},
        )
        self.assertEqual(response.status_code, 200)
        contact = Contact.objects.get(pk=response.json()["id"])
        self.assertTrue(contact.is_supplier)

    def test_modali_presenti_nel_form_preventivo(self):
        response = self.client.get(reverse("sales:quote_create"))
        self.assertContains(response, "quick-contact-modal")
        self.assertContains(response, "quick-product-modal")
        self.assertContains(response, "data-quick-product")
        self.assertContains(response, "data-autocomplete=")
        self.assertContains(response, "autocomplete-wrap")
        self.assertContains(response, 'name="tax_code"')

    def test_ricerca_articoli(self):
        product = Product.objects.create(
            name="Bullone M10 zincato",
            code="ARTM10",
            uom=self.uom,
            sale_price="0.50",
            sale_vat=self.vat,
            purchase_price="0.25",
            purchase_vat=self.vat,
            barcode="8012345678901",
        )

        by_name = self.client.get(reverse("catalog:search"), {"q": "bullone"})
        self.assertEqual(by_name.status_code, 200)
        results = by_name.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], product.pk)
        self.assertIn("ARTM10", results[0]["label"])
        self.assertIn("0,50 €", results[0]["extra"])

        by_barcode = self.client.get(reverse("catalog:search"), {"q": "8012345678901"})
        self.assertEqual(by_barcode.json()["results"][0]["id"], product.pk)

        purchase_context = self.client.get(reverse("catalog:search"), {"q": "bullone", "context": "purchase"})
        self.assertIn("0,25 €", purchase_context.json()["results"][0]["extra"])

        no_results = self.client.get(reverse("catalog:search"), {"q": "inesistente"})
        self.assertEqual(no_results.json()["results"], [])
