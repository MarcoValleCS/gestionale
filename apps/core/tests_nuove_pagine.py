"""Test delle pagine aggiunte: ricerca, scadenzario, follow-up, email, registro."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import PurchaseInvoice, SalesInvoice
from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import ActivityLog, UnitOfMeasure, VatRate
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
from apps.sales.models import Quote, QuoteLine, SalesOrder

Utente = get_user_model()


class PagineTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.vendite = Utente.objects.create_user("venditore", password="password123!")
        cls.vendite.groups.add(Group.objects.get(name="Vendite"))
        cls.magazzino = Utente.objects.create_user("magazziniere", password="password123!")
        cls.magazzino.groups.add(Group.objects.get(name="Magazzino"))

        cls.pz = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.cliente = Contact.objects.create(
            name="Cliente Scadenze srl", is_customer=True, email="cliente@example.it", city="Bergamo"
        )
        cls.fornitore = Contact.objects.create(name="Fornitore Test spa", is_customer=False, is_supplier=True)
        cls.articolo = Product.objects.create(
            code="ART.TEST", name="Articolo di prova", barcode="8012345678901",
            uom=cls.pz, sale_price=Decimal("100"), sale_vat=cls.vat,
            purchase_price=Decimal("60"), purchase_vat=cls.vat,
        )

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)


class RicercaGlobaleTest(PagineTestBase):
    def test_trova_contatti_articoli_e_documenti(self):
        self.login()
        preventivo = Quote.objects.create(number="PRE-001", customer=self.cliente)
        QuoteLine.objects.create(quote=preventivo, product=self.articolo, description="x", qty=Decimal("1"), uom=self.pz, unit_price=Decimal("100"), vat_rate=self.vat)
        preventivo.recalculate()

        response = self.client.get(reverse("core:search") + "?q=Scadenze")
        self.assertContains(response, "Cliente Scadenze srl")

        response = self.client.get(reverse("core:search") + "?q=ART.TEST")
        self.assertContains(response, "Articolo di prova")

        # anche per codice a barre
        response = self.client.get(reverse("core:search") + "?q=8012345678901")
        self.assertContains(response, "Articolo di prova")

        # e per numero documento
        response = self.client.get(reverse("core:search") + "?q=PRE-001")
        self.assertContains(response, "PRE-001")

    def test_ricerca_troppo_corta_non_cerca(self):
        self.login()
        response = self.client.get(reverse("core:search") + "?q=S")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cliente Scadenze srl")

    def test_il_magazziniere_non_vede_i_preventivi(self):
        preventivo = Quote.objects.create(number="PRE-002", customer=self.cliente)
        self.login(self.magazzino)
        response = self.client.get(reverse("core:search") + "?q=PRE-002")
        self.assertEqual(response.status_code, 200)
        # il numero compare nel campo di ricerca, ma non come risultato
        self.assertNotContains(response, reverse("sales:quote_detail", args=[preventivo.pk]))

    def test_la_ricerca_e_nella_barra_in_alto(self):
        self.login()
        self.assertContains(self.client.get(reverse("core:home")), "Cerca in tutto il gestionale")


class ScadenzarioTest(PagineTestBase):
    def fattura(self, numero, giorni_scadenza, stato=SalesInvoice.STATUS_ISSUED, importo="1220.00", scadenza=True):
        fattura = SalesInvoice.objects.create(
            number=numero, date=timezone.localdate() - timedelta(days=40),
            customer=self.cliente, status=stato,
        )
        fattura.lines.create(
            description="Voce", qty=Decimal("1"), uom=self.pz,
            unit_price=Decimal(importo), vat_rate=self.vat,
        )
        fattura.recalculate()
        if scadenza:
            fattura.due_date = timezone.localdate() + timedelta(days=giorni_scadenza)
            fattura.save(update_fields=["due_date"])
        return fattura

    def test_mostra_scadute_e_fasce(self):
        self.fattura("FT-1", -10)   # scaduta
        self.fattura("FT-2", 10)    # entro 30
        self.fattura("FT-3", 200)   # oltre 90
        self.login()
        response = self.client.get(reverse("billing:scadenzario"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for numero in ("FT-1", "FT-2", "FT-3"):
            self.assertIn(numero, html)
        self.assertIn("Scadute", html)
        self.assertIn("Oltre 90 giorni", html)

    def test_filtro_solo_scadute(self):
        self.fattura("FT-1", -10)
        self.fattura("FT-2", 10)
        self.login()
        response = self.client.get(reverse("billing:scadenzario") + "?scadute=1")
        html = response.content.decode()
        self.assertIn("FT-1", html)
        self.assertNotIn("FT-2", html)

    def test_non_mostra_le_fatture_incassate(self):
        self.fattura("FT-PAGATA", -10, stato=SalesInvoice.STATUS_PAID)
        self.login()
        self.assertNotContains(self.client.get(reverse("billing:scadenzario")), "FT-PAGATA")

    def test_mostra_i_pagamenti_ai_fornitori(self):
        fattura = PurchaseInvoice.objects.create(
            number="FA-1", date=timezone.localdate() - timedelta(days=40),
            supplier=self.fornitore, status=PurchaseInvoice.STATUS_REGISTERED,
            due_date=timezone.localdate() - timedelta(days=5),
        )
        fattura.lines.create(description="Voce", qty=Decimal("1"), uom=self.pz, unit_price=Decimal("500"), vat_rate=self.vat)
        fattura.recalculate()
        self.login()
        response = self.client.get(reverse("billing:scadenzario"))
        self.assertContains(response, "FA-1")
        self.assertContains(response, "Fornitore Test spa")

    def test_sollecito_senza_email_avvisa(self):
        fattura = self.fattura("FT-1", -10)
        fattura.customer.email = ""
        fattura.customer.save(update_fields=["email"])
        self.login()
        response = self.client.post(reverse("billing:salesinvoice_reminder", args=[fattura.pk]), follow=True)
        self.assertContains(response, "non ha un indirizzo email")

    @override_settings(EMAIL_IS_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_sollecito_inviato(self):
        fattura = self.fattura("FT-1", -10)
        self.login()
        response = self.client.post(reverse("billing:salesinvoice_reminder", args=[fattura.pk]), follow=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("FT-1", mail.outbox[0].subject)
        self.assertContains(response, "Sollecito inviato")

    def test_vendite_accede_il_magazziniere_no(self):
        self.login(self.vendite)
        self.assertEqual(self.client.get(reverse("billing:scadenzario")).status_code, 200)
        self.login(self.magazzino)
        self.assertEqual(self.client.get(reverse("billing:scadenzario")).status_code, 403)


class FollowUpTest(PagineTestBase):
    def preventivo(self, numero, giorni_fa, stato=Quote.STATUS_SENT):
        preventivo = Quote.objects.create(
            number=numero, date=timezone.localdate() - timedelta(days=giorni_fa),
            valid_until=timezone.localdate() - timedelta(days=giorni_fa - 30),
            customer=self.cliente, status=stato,
        )
        QuoteLine.objects.create(
            quote=preventivo, product=self.articolo, description="x",
            qty=Decimal("1"), uom=self.pz, unit_price=Decimal("100"), vat_rate=self.vat,
        )
        preventivo.recalculate()
        return preventivo

    def test_mostra_i_preventivi_fermi(self):
        self.preventivo("PRE-VECCHIO", 20)
        self.preventivo("PRE-NUOVO", 2)
        self.login()
        response = self.client.get(reverse("sales:follow_up") + "?giorni=7")
        html = response.content.decode()
        self.assertIn("PRE-VECCHIO", html)
        self.assertNotIn("PRE-NUOVO", html)
        self.assertIn("20 giorni", html)

    def test_conversione_e_valore(self):
        self.preventivo("PRE-1", 30)
        convertito = self.preventivo("PRE-2", 60, stato=Quote.STATUS_CONVERTED)
        self.preventivo("PRE-3", 45, stato=Quote.STATUS_REJECTED)
        self.login()
        response = self.client.get(reverse("sales:follow_up"))
        self.assertEqual(response.context["convertiti"], 1)
        self.assertEqual(response.context["rifiutati"], 1)
        self.assertEqual(response.context["conversione"], 50.0)
        self.assertGreater(response.context["valore_fermo"], 0)

    def test_preventivo_scaduto_segnalato(self):
        self.preventivo("PRE-SCADUTO", 60)
        self.login()
        self.assertContains(self.client.get(reverse("sales:follow_up")), "scaduto")

    @override_settings(EMAIL_IS_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_sollecito_preventivo(self):
        preventivo = self.preventivo("PRE-1", 20)
        self.login()
        response = self.client.post(reverse("sales:quote_reminder", args=[preventivo.pk]), follow=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PRE-1", mail.outbox[0].subject)
        self.assertContains(response, "Sollecito inviato")


class ImpostazioniEmailTest(PagineTestBase):
    def test_pagina_admin(self):
        self.login()
        response = self.client.get(reverse("core:email_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stato dell'invio email")
        self.assertContains(response, "non è configurato")

    def test_non_admin_non_accede(self):
        self.login(self.vendite)
        self.assertEqual(self.client.get(reverse("core:email_settings")).status_code, 403)

    @override_settings(EMAIL_IS_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invio_di_prova(self):
        self.login()
        response = self.client.post(reverse("core:email_settings"), {"to": "prova@example.it"}, follow=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prova@example.it"])
        self.assertContains(response, "Email di prova inviata")

    def test_senza_configurazione_avvisa(self):
        self.login()
        response = self.client.post(reverse("core:email_settings"), {"to": "prova@example.it"}, follow=True)
        self.assertContains(response, "non è configurato")


class RegistroAttivitaTest(PagineTestBase):
    def test_le_modifiche_finiscono_nel_registro(self):
        self.login()
        # creo un preventivo dal modulo
        response = self.client.post(
            reverse("sales:quote_create"),
            {
                "customer": self.cliente.pk,
                "date": timezone.localdate().isoformat(),
                "valid_until": "",
                "payment_term": "",
                "reference": "",
                "notes": "",
                "terms_text": "",
                "commission_contact": "",
                "commission_pct": "0",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-product": self.articolo.pk,
                "lines-0-description": "Articolo di prova",
                "lines-0-section": "",
                "lines-0-qty": "1",
                "lines-0-uom": self.pz.pk,
                "lines-0-unit_price": "100",
                "lines-0-discount_pct": "0",
                "lines-0-vat_rate": self.vat.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        voce = ActivityLog.objects.filter(model_name="Preventivo", action="creato").first()
        self.assertIsNotNone(voce, "il preventivo creato deve comparire nel registro")
        self.assertEqual(voce.user, self.admin)

    def test_la_modifica_registra_i_campi_cambiati(self):
        self.login()
        preventivo = Quote.objects.create(number="PRE-1", customer=self.cliente)
        ActivityLog.objects.all().delete()
        preventivo.reference = "Rif. nuovo"
        preventivo.save()
        voce = ActivityLog.objects.filter(action="modificato").first()
        self.assertIsNotNone(voce)
        self.assertIn("reference", voce.details)

    def test_la_cancellazione_viene_registrata(self):
        self.login()
        articolo = Product.objects.create(name="Da cancellare", uom=self.pz, sale_vat=self.vat, purchase_vat=self.vat)
        ActivityLog.objects.all().delete()
        articolo.delete()
        self.assertTrue(ActivityLog.objects.filter(action="cancellato", object_label__contains="Da cancellare").exists())

    def test_pagina_del_registro_con_filtri(self):
        self.login()
        Quote.objects.create(number="PRE-1", customer=self.cliente)
        response = self.client.get(reverse("core:activity_log"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRE-1")
        response = self.client.get(reverse("core:activity_log") + "?azione=creato&tipo=Preventivo")
        self.assertContains(response, "PRE-1")
        response = self.client.get(reverse("core:activity_log") + "?azione=cancellato")
        self.assertNotContains(response, "PRE-1")

    def test_solo_admin_vede_il_registro(self):
        self.login(self.vendite)
        self.assertEqual(self.client.get(reverse("core:activity_log")).status_code, 403)

