"""Test di DDT, fatture emesse e ricevute."""
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

from . import sdi, services
from .models import DeliveryNote, PurchaseInvoice, SalesInvoice

User = get_user_model()


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

    def test_email_precompilata_dal_modello(self):
        from apps.core.models import EmailTemplate

        invoice = self.issued_invoice()
        EmailTemplate.objects.create(
            kind=EmailTemplate.KIND_INVOICE, subject="Fattura personalizzata {numero}", body="Corpo per {cliente}"
        )
        self.login()
        risposta = self.client.get(reverse("billing:salesinvoice_detail", args=[invoice.pk]))
        self.assertContains(risposta, "Fattura personalizzata")
        self.assertContains(risposta, "Corpo per")

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
        from django.core.management import call_command

        from apps.core.models import EmailInCoda

        invoice = self.issued_invoice()
        self.login()
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_IS_CONFIGURED=True
        ), mock.patch("apps.billing.emailing.render_invoice_pdf", return_value=b"%PDF-1.4 finto"):
            response = self.client.post(
                reverse("billing:salesinvoice_email", args=[invoice.pk]),
                {"to": "cliente@example.com", "subject": "Fattura di prova", "message": "Buongiorno"},
                follow=True,
            )
        from django.core import mail

        # La pagina accoda; spedisce il comando in background.
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "accodata per cliente@example.com")
        voce = EmailInCoda.objects.get()
        self.assertEqual(voce.stato, EmailInCoda.STATO_ATTESA)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SalesInvoice.STATUS_ISSUED)
        call_command("invia_coda_email")
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
            response = self.client.post(reverse("billing:salesinvoice_sdi_send", args=[invoice.pk]), follow=True)
        from django.core import mail
        from django.core.management import call_command

        from apps.core.models import EmailInCoda

        # La pagina accoda l'XML; lo trasmette il comando in background.
        self.assertContains(response, "accodata per lo SDI")
        invoice.refresh_from_db()
        self.assertEqual(invoice.sdi_status, SalesInvoice.SDI_GENERATED)
        self.assertEqual(EmailInCoda.objects.count(), 1)
        call_command("invia_coda_email")
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


class SalAccontiTest(BillingTestBase):
    """Fatturazione lavori: acconti, SAL e saldo su un cantiere."""

    def setUp(self):
        from apps.jobs.models import Job

        self.job = Job.objects.create(name="Piscina Via Verdi", customer=self.customer)
        self.order = SalesOrder.objects.create(customer=self.customer, job=self.job)
        self.order.lines.create(
            product=self.product, description="Lavori piscina", qty=Decimal("100"),
            uom=self.uom, unit_price=Decimal("10.00"), vat_rate=self.vat22,
        )
        self.order.recalculate()
        sales_services.confirm_sales_order(self.order, user=self.user)

    def test_valore_contratto(self):
        self.assertEqual(services.contract_amount_for(self.job), Decimal("1000.00"))

    def test_acconto_sal_saldo(self):
        acconto = services.create_job_invoice(self.job, SalesInvoice.KIND_ADVANCE, percent=Decimal("30"), user=self.user)
        self.assertEqual(acconto.subtotal, Decimal("300.00"))
        self.assertEqual(acconto.kind, SalesInvoice.KIND_ADVANCE)

        sal = services.create_job_invoice(self.job, SalesInvoice.KIND_SAL, percent=Decimal("50"), user=self.user)
        self.assertEqual(sal.sal_number, 1)
        self.assertEqual(sal.subtotal, Decimal("200.00"), "50% del contratto meno l'acconto già fatturato")

        saldo = services.create_job_invoice(self.job, SalesInvoice.KIND_BALANCE, user=self.user)
        self.assertEqual(saldo.subtotal, Decimal("500.00"))

        riepilogo = services.job_billing_summary(self.job)
        self.assertEqual(riepilogo["committed"], Decimal("1000.00"))
        self.assertEqual(riepilogo["residual"], Decimal("0"))

    def test_avanzamento_gia_fatturato(self):
        services.create_job_invoice(self.job, SalesInvoice.KIND_SAL, percent=Decimal("100"), user=self.user)
        with self.assertRaises(ValidationError):
            services.create_job_invoice(self.job, SalesInvoice.KIND_SAL, percent=Decimal("100"), user=self.user)

    def test_vista_crea_sal_dal_cantiere(self):
        self.login()
        risposta = self.client.post(
            reverse("billing:salesinvoice_from_job", args=[self.job.pk]), {"tipo": "sal", "percento": "30"}
        )
        self.assertEqual(risposta.status_code, 302)
        fattura = SalesInvoice.objects.get(job=self.job, kind=SalesInvoice.KIND_SAL)
        self.assertEqual(fattura.subtotal, Decimal("300.00"))
        self.assertEqual(fattura.sal_number, 1)

    def test_scheda_cantiere_mostra_fatturazione(self):
        self.login()
        risposta = self.client.get(reverse("jobs:job_detail", args=[self.job.pk]))
        self.assertEqual(risposta.status_code, 200)
        self.assertContains(risposta, "Fatturazione")


class SalSdiTest(EmailAndSdiTest):
    """Tipo documento SDI: TD02 per gli acconti, TD01 per SAL e saldi."""

    def setUp(self):
        from apps.jobs.models import Job

        self.job = Job.objects.create(name="Piscina SDI", customer=self.customer)
        self.order = SalesOrder.objects.create(customer=self.customer, job=self.job)
        self.order.lines.create(
            product=self.product, description="Lavori", qty=Decimal("100"),
            uom=self.uom, unit_price=Decimal("10.00"), vat_rate=self.vat22,
        )
        self.order.recalculate()
        sales_services.confirm_sales_order(self.order, user=self.user)
        self.customer.sdi_code = "ABC1234"
        self.customer.save(update_fields=["sdi_code"])

    def _tipo_documento(self, invoice):
        root = ET.fromstring(sdi.build_fattura_xml(invoice))
        return root.findtext(
            "f:FatturaElettronicaBody/f:DatiGenerali/f:DatiGeneraliDocumento/f:TipoDocumento",
            namespaces={"f": sdi.NS},
        )

    def test_tipi_documento(self):
        acconto = services.create_job_invoice(self.job, SalesInvoice.KIND_ADVANCE, percent=Decimal("30"), user=self.user)
        services.issue_sales_invoice(acconto)
        self.assertEqual(self._tipo_documento(acconto), "TD02")

        sal = services.create_job_invoice(self.job, SalesInvoice.KIND_SAL, percent=Decimal("50"), user=self.user)
        services.issue_sales_invoice(sal)
        self.assertEqual(self._tipo_documento(sal), "TD01")

        root = ET.fromstring(sdi.build_fattura_xml(sal))
        causale = root.findtext(
            "f:FatturaElettronicaBody/f:DatiGenerali/f:DatiGeneraliDocumento/f:Causale", namespaces={"f": sdi.NS}
        )
        self.assertIn("SAL n. 1", causale)


class AccontoOrdineTest(BillingTestBase):
    """Acconto e resto su un ordine normale (non cantiere)."""

    def setUp(self):
        self.order = self.confirmed_order("300")  # 300 × 10,00 € = 3.000 €

    def test_acconto_riduce_le_voci_del_30_percento(self):
        fattura = services.create_order_advance(self.order, Decimal("30"), user=self.user)
        self.assertEqual(fattura.kind, SalesInvoice.KIND_ADVANCE)
        self.assertEqual(fattura.source_order, self.order)
        self.assertEqual(fattura.subtotal, Decimal("900.00"))
        riga = fattura.lines.get()
        self.assertEqual(riga.qty, Decimal("90.000"), "quantità dell'ordine ridotta del 30%")
        self.assertEqual(riga.unit_price, Decimal("10.00"))

    def test_fattura_il_resto(self):
        services.create_order_advance(self.order, Decimal("30"), user=self.user)
        resto = services.create_order_balance(self.order, user=self.user)
        self.assertEqual(resto.subtotal, Decimal("2100.00"))
        self.assertEqual(resto.lines.get().qty, Decimal("210.000"))

        riepilogo = services.order_billing_summary(self.order)
        self.assertEqual(riepilogo["committed"], Decimal("3000.00"))
        self.assertEqual(riepilogo["residual"], Decimal("0"))

    def test_acconto_oltre_il_residuo(self):
        services.create_order_advance(self.order, Decimal("70"), user=self.user)
        with self.assertRaises(ValidationError):
            services.create_order_advance(self.order, Decimal("50"), user=self.user)

    def test_vista_acconto_e_resto(self):
        self.login()
        risposta = self.client.post(
            reverse("billing:salesinvoice_from_order", args=[self.order.pk]), {"tipo": "advance", "percento": "30"}
        )
        self.assertEqual(risposta.status_code, 302)
        acconto = SalesInvoice.objects.get(source_order=self.order, kind=SalesInvoice.KIND_ADVANCE)
        self.assertEqual(acconto.subtotal, Decimal("900.00"))

        risposta = self.client.post(
            reverse("billing:salesinvoice_from_order", args=[self.order.pk]), {"tipo": "balance"}
        )
        self.assertEqual(risposta.status_code, 302)
        resto = SalesInvoice.objects.get(source_order=self.order, kind=SalesInvoice.KIND_BALANCE)
        self.assertEqual(resto.subtotal, Decimal("2100.00"))


class AccontoFissoTest(BillingTestBase):
    """Acconto a importo fisso scalato dalle fatture delle consegne.

    Esempio: ordine 3.000 €, acconto 1.000 €. Consegna da 300 € → fattura a 0 €
    (300 scalati); consegna da 700 € → fattura a 0 € (acconto esaurito);
    consegne successive fatturate per intero.
    """

    def setUp(self):
        self.order = self.confirmed_order("300")  # 300 × 10,00 € = 3.000 €
        register_movement(product=self.product, delta=Decimal("300"), movement_type="load", user=self.user)

    def _fattura_consegna(self, qty):
        nota = services.create_delivery_note_from_order(self.order, user=self.user)
        riga = nota.lines.get()
        riga.qty = Decimal(qty)
        riga.save(update_fields=["qty"])
        errors = services.issue_delivery_note(nota, user=self.user)
        self.assertEqual(errors, [])
        return services.create_sales_invoice_from_delivery_note(nota, user=self.user)

    def test_acconto_importo_fisso(self):
        acconto = services.create_order_advance(self.order, amount=Decimal("1000"), user=self.user)
        self.assertEqual(acconto.kind, SalesInvoice.KIND_ADVANCE)
        self.assertEqual(acconto.subtotal, Decimal("1000.00"))
        self.assertEqual(acconto.lines.count(), 1)
        self.assertIsNone(acconto.lines.get().product_id)
        riepilogo = services.order_billing_summary(self.order)
        self.assertEqual(riepilogo["advance_remaining"], Decimal("1000.00"))

    def test_acconto_fisso_oltre_il_residuo(self):
        with self.assertRaises(ValidationError):
            services.create_order_advance(self.order, amount=Decimal("4000"), user=self.user)
        with self.assertRaises(ValidationError):
            services.create_order_advance(self.order, amount=Decimal("0"), user=self.user)

    def test_scalo_progressivo_fino_a_esaurimento(self):
        services.create_order_advance(self.order, amount=Decimal("1000"), user=self.user)

        prima = self._fattura_consegna("30")  # merci 300 €
        self.assertEqual(prima.subtotal, Decimal("0.00"))
        storno = prima.lines.get(is_advance_deduction=True)
        self.assertEqual(storno.unit_price, Decimal("-300.00"))
        self.assertEqual(services.order_billing_summary(self.order)["advance_remaining"], Decimal("700.00"))

        seconda = self._fattura_consegna("70")  # merci 700 €
        self.assertEqual(seconda.subtotal, Decimal("0.00"))
        self.assertEqual(services.order_billing_summary(self.order)["advance_remaining"], Decimal("0.00"))

        terza = self._fattura_consegna("200")  # merci 2.000 €, acconto esaurito
        self.assertEqual(terza.subtotal, Decimal("2000.00"))
        self.assertFalse(terza.lines.filter(is_advance_deduction=True).exists())

        riepilogo = services.order_billing_summary(self.order)
        self.assertEqual(riepilogo["committed"], Decimal("3000.00"))
        self.assertEqual(riepilogo["residual"], Decimal("0"))

    def test_acconto_percentuale_non_alimenta_il_monte(self):
        services.create_order_advance(self.order, Decimal("10"), user=self.user)
        fattura = self._fattura_consegna("30")
        self.assertFalse(fattura.lines.filter(is_advance_deduction=True).exists())
        self.assertEqual(fattura.subtotal, Decimal("300.00"))

    def test_acconto_annullato_non_conta(self):
        acconto = services.create_order_advance(self.order, amount=Decimal("1000"), user=self.user)
        SalesInvoice.objects.filter(pk=acconto.pk).update(status=SalesInvoice.STATUS_CANCELLED)
        fattura = self._fattura_consegna("30")
        self.assertFalse(fattura.lines.filter(is_advance_deduction=True).exists())
        self.assertEqual(services.order_billing_summary(self.order)["advance_remaining"], Decimal("0"))

    def test_vista_acconto_importo_fisso(self):
        self.login()
        risposta = self.client.post(
            reverse("billing:salesinvoice_from_order", args=[self.order.pk]),
            {"tipo": "advance", "importo": "1000"},
        )
        self.assertEqual(risposta.status_code, 302)
        acconto = SalesInvoice.objects.get(source_order=self.order, kind=SalesInvoice.KIND_ADVANCE)
        self.assertEqual(acconto.subtotal, Decimal("1000.00"))
        pagina = self.client.get(reverse("sales:order_detail", args=[self.order.pk])).content.decode("utf-8")
        self.assertIn("Acconto da scalare", pagina)
