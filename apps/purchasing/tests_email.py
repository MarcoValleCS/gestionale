"""Test invio email degli ordini fornitore."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import EmailInCoda, UnitOfMeasure, VatRate

from .models import PurchaseOrder

User = get_user_model()


class PoEmailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.user.email = "ufficio@aquaforma.it"
        cls.user.save(update_fields=["email"])
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat22 = VatRate.objects.get(code="22")
        cls.supplier = Contact.objects.create(
            name="Fornitore Email S.p.A.", is_customer=False, is_supplier=True, email="ordini@fornitore.it"
        )
        cls.product = Product.objects.create(
            name="Rubinetto",
            uom=cls.uom,
            sale_price=Decimal("10.00"),
            sale_vat=cls.vat22,
            purchase_price=Decimal("5.00"),
            purchase_vat=cls.vat22,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _ordine(self):
        order = PurchaseOrder.objects.create(supplier=self.supplier)
        order.lines.create(
            product=self.product, description=self.product.name, qty=Decimal("4"),
            uom=self.uom, unit_price=Decimal("5.00"), vat_rate=self.vat22,
        )
        order.recalculate()
        return order

    def test_scheda_mostra_form_email(self):
        order = self._ordine()
        pagina = self.client.get(reverse("purchasing:po_detail", args=[order.pk])).content.decode("utf-8")
        self.assertIn("Invia al fornitore", pagina)
        self.assertIn(f"Ordine {order.number}", pagina)

    def _fornitore_con_agenzia(self):
        self.supplier.agency_name = "Rappresentanze Rossi"
        self.supplier.agent_name = "Mario Rossi"
        self.supplier.agent_phone = "035 123456"
        self.supplier.agent_email = "agente@agenzia.it"
        self.supplier.save(update_fields=["agency_name", "agent_name", "agent_phone", "agent_email"])

    def test_scheda_offre_la_scelta_dellagenzia(self):
        """Con i dati agenzia compare la scelta tra agenzia e fornitore."""
        self._fornitore_con_agenzia()
        order = self._ordine()
        pagina = self.client.get(reverse("purchasing:po_detail", args=[order.pk])).content.decode("utf-8")
        self.assertIn('name="destinatario"', pagina)
        self.assertIn('value="agenzia"', pagina)
        self.assertIn("Rappresentanze Rossi", pagina)
        self.assertIn("agente@agenzia.it", pagina)

    @override_settings(EMAIL_IS_CONFIGURED=True)
    def test_email_allagenzia_quando_scelta(self):
        self._fornitore_con_agenzia()
        order = self._ordine()
        risposta = self.client.post(
            reverse("purchasing:po_email", args=[order.pk]),
            {
                "destinatario": "agenzia",
                "to": "ordini@fornitore.it",
                "subject": "Ordine prova",
                "message": "In allegato.",
            },
        )
        self.assertEqual(risposta.status_code, 302)
        voce = EmailInCoda.objects.get(oggetto_id=order.pk, modello=EmailInCoda.MODELLO_ORDINE_FORNITORE)
        self.assertEqual(voce.to_email, "agente@agenzia.it")

    @override_settings(EMAIL_IS_CONFIGURED=True)
    def test_scelta_fornitore_anche_con_agenzia_compilata(self):
        self._fornitore_con_agenzia()
        order = self._ordine()
        self.client.post(
            reverse("purchasing:po_email", args=[order.pk]),
            {
                "destinatario": "fornitore",
                "to": "ordini@fornitore.it",
                "subject": "Ordine prova",
                "message": "In allegato.",
            },
        )
        voce = EmailInCoda.objects.get(oggetto_id=order.pk, modello=EmailInCoda.MODELLO_ORDINE_FORNITORE)
        self.assertEqual(voce.to_email, "ordini@fornitore.it")

    @override_settings(EMAIL_IS_CONFIGURED=True)
    def test_email_accodata_con_pdf_e_mittente(self):
        order = self._ordine()
        risposta = self.client.post(
            reverse("purchasing:po_email", args=[order.pk]),
            {"to": "ordini@fornitore.it", "subject": "Ordine prova", "message": "In allegato."},
        )
        self.assertEqual(risposta.status_code, 302)
        voce = EmailInCoda.objects.get(oggetto_id=order.pk, modello=EmailInCoda.MODELLO_ORDINE_FORNITORE)
        self.assertEqual(voce.to_email, "ordini@fornitore.it")
        self.assertEqual(voce.from_email, "ufficio@aquaforma.it")
        self.assertTrue(voce.attachment_name.endswith(".pdf"))

    def test_email_senza_destinatario(self):
        order = self._ordine()
        order.supplier.email = ""
        order.supplier.save(update_fields=["email"])
        risposta = self.client.post(
            reverse("purchasing:po_email", args=[order.pk]), {"to": "", "subject": "x", "message": "y"},
            follow=True,
        )
        self.assertEqual(risposta.status_code, 200)
        self.assertFalse(EmailInCoda.objects.filter(oggetto_id=order.pk).exists())

    def test_scarica_pdf(self):
        from apps.core.pdf import pdf_available

        order = self._ordine()
        risposta = self.client.get(reverse("purchasing:po_pdf", args=[order.pk]))
        if not pdf_available():
            self.assertEqual(risposta.status_code, 302)
            return
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(risposta.streaming_content).startswith(b"%PDF-"))
