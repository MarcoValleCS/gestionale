"""Test di DDT, fatture emesse/ricevute e acquisizione OCR."""
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from unittest import mock
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.inventory.models import StockLevel, Warehouse
from apps.inventory.services import register_movement
from apps.purchasing.models import PurchaseOrder
from apps.sales import services as sales_services
from apps.sales.models import SalesOrder

from . import ocr, sdi, services
from .models import DeliveryNote, PurchaseInvoice, SalesInvoice, ScannedDocument

User = get_user_model()

OCR_TEXT = """FERRAMENTA BIANCHI S.P.A.
Via Roma 1 - Torino
P.IVA 09876543210
DDT n. 245/2026 del 28/09/2026
Bullone M8 zincato PZ 10,00
Tondino ferro 8 mm PZ 5,00
Totale documento 1.234,56
"""


class BillingTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat22 = VatRate.objects.get(code="22")
        cls.warehouse = Warehouse.get_default()
        cls.customer = Contact.objects.create(name="Cliente DDT S.r.l.", is_customer=True)
        cls.supplier = Contact.objects.create(
            name="Ferramenta Bianchi S.p.A.", is_customer=False, is_supplier=True, vat_number="09876543210"
        )
        cls.product = Product.objects.create(
            name="Bullone M8",
            uom=cls.uom,
            sale_price=Decimal("10.00"),
            sale_vat=cls.vat22,
            purchase_price=Decimal("5.00"),
            purchase_vat=cls.vat22,
            main_supplier=cls.supplier,
        )

    def login(self):
        self.client.force_login(self.user)

    def confirmed_order(self, qty="8"):
        order = SalesOrder.objects.create(customer=self.customer)
        order.lines.create(
            product=self.product, description=self.product.name, qty=Decimal(qty),
            uom=self.uom, unit_price=Decimal("10.00"), vat_rate=self.vat22,
        )
        order.recalculate()
        sales_services.confirm_sales_order(order, user=self.user)
        return order


class DeliveryNoteTest(BillingTestBase):
    def test_ddt_da_ordine_con_scarico_magazzino(self):
        register_movement(product=self.product, delta=Decimal("5"), movement_type="load", user=self.user)
        order = self.confirmed_order("8")

        # carenza 3 → ordine fornitore generato; lo ricevo tutto
        po = PurchaseOrder.objects.get()
        from apps.purchasing.services import receive_purchase_order

        receive_purchase_order(po, {str(po.lines.get().pk): Decimal("3")}, user=self.user)

        note = services.create_delivery_note_from_order(order, user=self.user)
        self.assertTrue(note.number.startswith("DDT-"))
        self.assertEqual(note.lines.count(), 1)
        self.assertEqual(note.lines.get().qty, Decimal("8"))

        errors = services.issue_delivery_note(note, user=self.user)
        self.assertEqual(errors, [])
        note.refresh_from_db()
        self.assertEqual(note.status, DeliveryNote.STATUS_ISSUED)

        level = StockLevel.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(level.quantity, Decimal("0"))

        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_DELIVERED)
        self.assertEqual(order.lines.get().qty_delivered, Decimal("8"))

    def test_ddt_bloccato_senza_giacenza(self):
        order = self.confirmed_order("2")  # nessuna giacenza
        note = services.create_delivery_note_from_order(order, user=self.user)
        errors = services.issue_delivery_note(note, user=self.user)
        self.assertEqual(len(errors), 1)
        note.refresh_from_db()
        self.assertEqual(note.status, DeliveryNote.STATUS_ISSUED)  # emesso ma riga non scaricata
        order.refresh_from_db()
        self.assertNotEqual(order.status, SalesOrder.STATUS_DELIVERED)

    def test_fattura_da_ddt_e_azioni(self):
        register_movement(product=self.product, delta=Decimal("5"), movement_type="load", user=self.user)
        order = self.confirmed_order("5")
        note = services.create_delivery_note_from_order(order, user=self.user)
        services.issue_delivery_note(note, user=self.user)

        invoice = services.create_sales_invoice_from_delivery_note(note, user=self.user)
        self.assertTrue(invoice.number.startswith("FT-"))
        self.assertEqual(invoice.grand_total, Decimal("61.00"))  # 50 + 22%
        note.refresh_from_db()
        self.assertTrue(note.invoiced)

        # non si può fatturare due volte
        with self.assertRaises(Exception):
            services.create_sales_invoice_from_delivery_note(note, user=self.user)

        services.issue_sales_invoice(invoice)
        services.mark_sales_invoice_sent(invoice)
        services.mark_sales_invoice_paid(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SalesInvoice.STATUS_PAID)
        self.assertIsNotNone(invoice.paid_at)


class PurchaseInvoiceTest(BillingTestBase):
    def test_fattura_da_ordine_fornitore(self):
        order = self.confirmed_order("4")  # genera ordine fornitore per 4
        po = PurchaseOrder.objects.get()
        invoice = services.create_purchase_invoice_from_po(po, user=self.user)
        self.assertTrue(invoice.number.startswith("FA-"))
        self.assertEqual(invoice.supplier, self.supplier)
        self.assertEqual(invoice.grand_total, Decimal("24.40"))  # 20 + 22%

        services.register_purchase_invoice(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, PurchaseInvoice.STATUS_REGISTERED)

        services.mark_purchase_invoice_paid(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, PurchaseInvoice.STATUS_PAID)


class OcrParsingTest(BillingTestBase):
    def test_lettura_dati_documento(self):
        data = ocr.parse_document_text(OCR_TEXT)
        self.assertEqual(data["doc_number"], "245/2026")
        self.assertEqual(data["doc_date"], date(2026, 9, 28))
        self.assertEqual(data["total_amount"], Decimal("1234.56"))
        self.assertEqual(data["supplier"], self.supplier)

    def test_lettura_righe(self):
        rows = ocr.guess_lines(OCR_TEXT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["description"], "Bullone M8 zincato")
        self.assertEqual(rows[0]["qty"], "10.00")

    def test_righe_con_quantita_prima(self):
        rows = ocr.guess_lines("Vaso sospeso bianco 2 PZ\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["qty"], "2")


class ScanWorkflowTest(BillingTestBase):
    def test_caricamento_ocr_e_creazione_fattura(self):
        self.login()
        with mock.patch("apps.billing.ocr.ocr_available", return_value=True), mock.patch(
            "apps.billing.ocr.extract_text", return_value=OCR_TEXT
        ):
            upload = SimpleUploadedFile("ddt_bianchi.jpg", b"finta-immagine", content_type="image/jpeg")
            response = self.client.post(reverse("billing:scan_upload"), {"file": upload})
        self.assertEqual(response.status_code, 302)
        scan = ScannedDocument.objects.get()
        self.assertEqual(scan.status, ScannedDocument.STATUS_OK)
        self.assertEqual(scan.supplier, self.supplier)
        self.assertEqual(scan.doc_number, "245/2026")
        self.assertEqual(scan.total_amount, Decimal("1234.56"))

        # crea la fattura dal documento
        response = self.client.post(reverse("billing:scan_create_invoice", args=[scan.pk]), {"supplier": self.supplier.pk})
        self.assertEqual(response.status_code, 302)
        invoice = PurchaseInvoice.objects.get()
        self.assertEqual(invoice.supplier, self.supplier)
        self.assertEqual(invoice.supplier_reference, "245/2026")
        self.assertEqual(invoice.lines.count(), 2)
        scan.refresh_from_db()
        self.assertEqual(scan.purchase_invoice, invoice)

    def test_ocr_non_disponibile(self):
        self.login()
        with mock.patch("apps.billing.ocr.ocr_available", return_value=False):
            upload = SimpleUploadedFile("ddt.jpg", b"finta", content_type="image/jpeg")
            self.client.post(reverse("billing:scan_upload"), {"file": upload})
        scan = ScannedDocument.objects.get()
        self.assertEqual(scan.status, ScannedDocument.STATUS_ERROR)
        self.assertIn("OCR non disponibile", scan.error_message)


class EmailAndSdiTest(BillingTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

        # Dati azienda e cliente completi per la fatturazione elettronica
        from apps.core.models import CompanySettings

        company = CompanySettings.load()
        company.vat_number = "01234567890"
        company.tax_code = "01234567890"
        company.address = "Via Test 1"
        company.zip_code = "20100"
        company.city = "Milano"
        company.province = "MI"
        company.pec = "azienda@pec.example.com"
        company.save()

        cls.customer.vat_number = "09876543210"
        cls.customer.tax_code = "09876543210"
        cls.customer.address = "Via Cliente 2"
        cls.customer.zip_code = "10100"
        cls.customer.city = "Torino"
        cls.customer.province = "TO"
        cls.customer.save()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    def issued_invoice(self):
        order = self.confirmed_order("2")
        invoice = services.create_sales_invoice_from_order(order, user=self.user)
        services.issue_sales_invoice(invoice)
        return invoice

    def test_composizione_xml_fatturapa(self):
        invoice = self.issued_invoice()
        self.customer.sdi_code = "ABC1234"
        self.customer.save(update_fields=["sdi_code"])

        xml = sdi.build_fattura_xml(invoice)
        root = ET.fromstring(xml)
        ns = {"f": sdi.NS}
        self.assertEqual(root.tag, f"{{{sdi.NS}}}FatturaElettronica")
        self.assertEqual(root.attrib["versione"], "FPR12")

        codice = root.findtext("f:FatturaElettronicaHeader/f:DatiTrasmissione/f:CodiceDestinatario", namespaces=ns)
        self.assertEqual(codice, "ABC1234")
        denominazione = root.findtext(
            "f:FatturaElettronicaHeader/f:CedentePrestatore/f:DatiAnagrafici/f:Anagrafica/f:Denominazione", namespaces=ns
        )
        self.assertEqual(denominazione, "La mia azienda")

        body = "f:FatturaElettronicaBody"
        self.assertEqual(
            root.findtext(f"{body}/f:DatiGenerali/f:DatiGeneraliDocumento/f:Numero", namespaces=ns), invoice.number
        )
        self.assertEqual(
            root.findtext(f"{body}/f:DatiGenerali/f:DatiGeneraliDocumento/f:ImportoTotaleDocumento", namespaces=ns),
            "24.40",  # 20 + 22%
        )
        lines = root.findall(f"{body}/f:DatiBeniServizi/f:DettaglioLinee", namespaces=ns)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].findtext("f:AliquotaIVA", namespaces=ns), "22.00")
        riepilogo = root.findall(f"{body}/f:DatiBeniServizi/f:DatiRiepilogo", namespaces=ns)
        self.assertEqual(len(riepilogo), 1)
        self.assertEqual(riepilogo[0].findtext("f:Imposta", namespaces=ns), "4.40")

    def test_xml_segnala_dati_mancanti(self):
        invoice = self.issued_invoice()
        self.customer.sdi_code = ""
        self.customer.pec = ""
        self.customer.save(update_fields=["sdi_code", "pec"])
        with self.assertRaises(ValidationError) as ctx:
            sdi.build_fattura_xml(invoice)
        self.assertTrue(any("codice destinatario" in message for message in ctx.exception.messages))

    def test_xml_con_aliquota_esente(self):
        vat_exempt = VatRate.objects.get(code="0")  # esente N1 dal seed
        invoice = self.issued_invoice()
        self.customer.sdi_code = "ABC1234"
        self.customer.save(update_fields=["sdi_code"])
        invoice.lines.create(
            invoice=invoice, position=2, description="Voce esente", qty=Decimal("1"),
            uom=self.uom, unit_price=Decimal("10.00"), vat_rate=vat_exempt,
        )
        invoice.recalculate()
        xml = sdi.build_fattura_xml(invoice)
        root = ET.fromstring(xml)
        ns = {"f": sdi.NS}
        nature = root.findall(f"f:FatturaElettronicaBody/f:DatiBeniServizi/f:DettaglioLinee/f:Natura", namespaces=ns)
        self.assertEqual(nature[0].text, "N1")

    def test_invio_email_con_pdf(self):
        invoice = self.issued_invoice()
        self.login()
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_IS_CONFIGURED=True
        ), mock.patch("apps.billing.emailing.render_invoice_pdf", return_value=b"%PDF-1.4 finto"):
            response = self.client.post(
                reverse("billing:salesinvoice_email", args=[invoice.pk]),
                {"to": "cliente@example.com", "subject": "Fattura di prova", "message": "Buongiorno"},
            )
        self.assertEqual(response.status_code, 302)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["cliente@example.com"])
        self.assertEqual(message.attachments[0][0], f"Fattura_{invoice.number}.pdf")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SalesInvoice.STATUS_SENT)

    def test_invio_email_non_configurato(self):
        invoice = self.issued_invoice()
        self.login()
        with override_settings(EMAIL_IS_CONFIGURED=False):
            response = self.client.post(
                reverse("billing:salesinvoice_email", args=[invoice.pk]),
                {"to": "cliente@example.com", "subject": "x", "message": "y"},
                follow=True,
            )
        self.assertContains(response, "Invio email non configurato")

    def test_generazione_invio_sdi_e_esito(self):
        invoice = self.issued_invoice()
        self.customer.sdi_code = "ABC1234"
        self.customer.save(update_fields=["sdi_code"])
        self.login()

        self.client.post(reverse("billing:salesinvoice_sdi_generate", args=[invoice.pk]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.sdi_status, SalesInvoice.SDI_GENERATED)
        self.assertTrue(invoice.xml_file.name.endswith(".xml"))

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_IS_CONFIGURED=True
        ):
            self.client.post(reverse("billing:salesinvoice_sdi_send", args=[invoice.pk]))
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to[0], "sdi01@pec.fatturapa.it")
        self.assertTrue(mail.outbox[0].attachments[0][0].startswith("IT"))
        self.assertIn("Fattura ABC1234", mail.outbox[0].subject)
        invoice.refresh_from_db()
        self.assertEqual(invoice.sdi_status, SalesInvoice.SDI_SENT)
        self.assertIsNotNone(invoice.sdi_sent_at)

        response = self.client.get(reverse("billing:salesinvoice_sdi_download", args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)

        self.client.post(
            reverse("billing:salesinvoice_sdi_status", args=[invoice.pk]),
            {"sdi_status": "accepted", "sdi_note": "Ricevuta accettazione"},
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.sdi_status, "accepted")
        self.assertEqual(invoice.sdi_note, "Ricevuta accettazione")


class BillingPagesSmokeTest(BillingTestBase):
    def test_pagine_e_azioni_da_ordine(self):
        register_movement(product=self.product, delta=Decimal("10"), movement_type="load", user=self.user)
        order = self.confirmed_order("5")
        self.login()

        # crea DDT dall'ordine tramite la vista
        response = self.client.post(reverse("billing:deliverynote_from_order", args=[order.pk]))
        note = DeliveryNote.objects.get()
        self.assertEqual(response.status_code, 302)

        po = PurchaseOrder.objects.create(supplier=self.supplier)
        po.lines.create(
            product=self.product, description=self.product.name, qty=Decimal("2"),
            uom=self.uom, unit_price=Decimal("5.00"), vat_rate=self.vat22,
        )
        po.recalculate()
        scan = ScannedDocument.objects.create(file=SimpleUploadedFile("scan.jpg", b"x"), uploaded_by=self.user)

        urls = [
            reverse("billing:deliverynote_list"),
            reverse("billing:deliverynote_create"),
            reverse("billing:deliverynote_detail", args=[note.pk]),
            reverse("billing:deliverynote_update", args=[note.pk]),
            reverse("billing:deliverynote_print", args=[note.pk]),
            reverse("billing:salesinvoice_list"),
            reverse("billing:salesinvoice_create"),
            reverse("billing:purchaseinvoice_list"),
            reverse("billing:purchaseinvoice_create"),
            reverse("billing:scan_list"),
            reverse("billing:scan_detail", args=[scan.pk]),
            reverse("core:home"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"{url} → {response.status_code}")

        # azioni fattura emessa da ordine
        response = self.client.post(reverse("billing:salesinvoice_from_order", args=[order.pk]))
        invoice = SalesInvoice.objects.get()
        self.assertEqual(response.status_code, 302)
        for url in [
            reverse("billing:salesinvoice_detail", args=[invoice.pk]),
            reverse("billing:salesinvoice_update", args=[invoice.pk]),
            reverse("billing:salesinvoice_print", args=[invoice.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        # fattura ricevuta da ordine fornitore
        response = self.client.post(reverse("billing:purchaseinvoice_from_po", args=[po.pk]))
        purchase = PurchaseInvoice.objects.get()
        self.assertEqual(response.status_code, 302)
        for url in [
            reverse("billing:purchaseinvoice_detail", args=[purchase.pk]),
            reverse("billing:purchaseinvoice_update", args=[purchase.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
