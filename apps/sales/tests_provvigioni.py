"""Test del resoconto mensile delle provvigioni."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate

from . import analytics
from .models import SalesOrder

User = get_user_model()


class CommissionReportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")

        cls.cliente = Contact.objects.create(name="Cliente Provvigioni", is_customer=True)
        cls.agente = Contact.objects.create(name="Agente Rossi", is_customer=False, is_supplier=True)
        cls.altro_agente = Contact.objects.create(name="Agente Bianchi", is_customer=False, is_supplier=True)

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)

    def ordine(self, numero, data, imponibile, agente, percentuale, consegnato=False):
        ordine = SalesOrder.objects.create(
            number=numero,
            date=data,
            customer=self.cliente,
            commission_contact=agente,
            commission_pct=Decimal(str(percentuale)),
            status=SalesOrder.STATUS_DELIVERED if consegnato else SalesOrder.STATUS_CONFIRMED,
        )
        ordine.lines.create(
            description="Voce",
            qty=Decimal("1"),
            uom=self.uom,
            unit_price=Decimal(str(imponibile)),
            vat_rate=self.vat,
        )
        ordine.recalculate()
        if consegnato:
            ordine.delivered_at = timezone.make_aware(datetime.combine(data, datetime.min.time()))
            ordine.save(update_fields=["delivered_at"])
        return ordine

    # ------------------------------------------------------------- calcolo
    def test_provvigione_calcolata_sull_imponibile(self):
        ordine = self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5)
        self.assertEqual(ordine.subtotal, Decimal("1000.00"))
        self.assertEqual(ordine.commission_amount, Decimal("50.00"))

    def test_resoconto_raggruppa_per_beneficiario(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5)
        self.ordine("OC-2", date(2026, 3, 20), "500", self.agente, 10)
        self.ordine("OC-3", date(2026, 3, 25), "2000", self.altro_agente, 2)

        report = analytics.commission_report(2026, 3)
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(report["rows"][0]["contact"], self.agente)  # ordinato per importo
        self.assertEqual(report["rows"][0]["commission"], Decimal("100.00"))  # 50 + 50
        self.assertEqual(report["rows"][0]["revenue"], Decimal("1500.00"))
        self.assertEqual(len(report["rows"][0]["orders"]), 2)
        self.assertEqual(report["rows"][1]["commission"], Decimal("40.00"))
        self.assertEqual(report["total_commission"], Decimal("140.00"))
        self.assertEqual(report["orders_count"], 3)

    def test_mesi_diversi_non_si_mescolano(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5)
        self.ordine("OC-2", date(2026, 4, 10), "1000", self.agente, 5)

        marzo = analytics.commission_report(2026, 3)
        aprile = analytics.commission_report(2026, 4)
        self.assertEqual(marzo["total_commission"], Decimal("50.00"))
        self.assertEqual(aprile["total_commission"], Decimal("50.00"))
        self.assertEqual(marzo["label"], "mar 2026")

    def test_ordini_consegnati_conteggiati_nel_mese_della_consegna(self):
        """Un ordine di marzo consegnato ad aprile matura ad aprile."""
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5, consegnato=True)
        ordine = SalesOrder.objects.get(number="OC-1")
        ordine.delivered_at = timezone.make_aware(datetime(2026, 4, 8, 9, 0))
        ordine.save(update_fields=["delivered_at"])

        marzo = analytics.commission_report(2026, 3)
        aprile = analytics.commission_report(2026, 4)
        self.assertEqual(marzo["orders_count"], 0)
        self.assertEqual(aprile["orders_count"], 1)
        self.assertEqual(aprile["total_paid"], Decimal("50.00"))
        self.assertEqual(aprile["total_pending"], Decimal("0"))

    def test_distinzione_tra_maturate_e_da_liquidare(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5, consegnato=True)
        self.ordine("OC-2", date(2026, 3, 20), "1000", self.agente, 5)
        report = analytics.commission_report(2026, 3)
        self.assertEqual(report["total_paid"], Decimal("50.00"))
        self.assertEqual(report["total_pending"], Decimal("50.00"))
        self.assertEqual(report["total_commission"], Decimal("100.00"))

    def test_filtro_per_stato(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5, consegnato=True)
        self.ordine("OC-2", date(2026, 3, 20), "1000", self.agente, 5)

        solo_consegnati = analytics.commission_report(2026, 3, analytics.STATO_CONSEGNATI)
        solo_confermati = analytics.commission_report(2026, 3, analytics.STATO_CONFERMATI)
        self.assertEqual(solo_consegnati["orders_count"], 1)
        self.assertEqual(solo_consegnati["total_commission"], Decimal("50.00"))
        self.assertEqual(solo_confermati["orders_count"], 1)
        self.assertEqual(solo_confermati["total_commission"], Decimal("50.00"))

    def test_ordini_senza_provvigione_esclusi(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", None, 0)
        report = analytics.commission_report(2026, 3)
        self.assertEqual(report["orders_count"], 0)
        self.assertEqual(report["total_commission"], Decimal("0"))

    def test_riepilogo_annuale(self):
        self.ordine("OC-1", date(2026, 2, 10), "1000", self.agente, 5)
        self.ordine("OC-2", date(2026, 3, 10), "1000", self.agente, 5)
        self.ordine("OC-3", date(2026, 11, 10), "1000", self.altro_agente, 10)

        anno = analytics.commission_year(2026)
        self.assertEqual(len(anno), 2)
        per_contatto = {voce["contact"]: voce for voce in anno}
        self.assertEqual(per_contatto[self.agente]["commission"], Decimal("100.00"))
        self.assertEqual(per_contatto[self.agente]["orders"], 2)
        self.assertEqual(per_contatto[self.altro_agente]["commission"], Decimal("100.00"))
        self.assertEqual(per_contatto[self.altro_agente]["orders"], 1)

    # -------------------------------------------------------------- pagina
    def test_pagina_resoconto(self):
        self.ordine("OC-1", date(2026, 3, 10), "1000", self.agente, 5)
        self.login()
        response = self.client.get(reverse("sales:commission_report") + "?anno=2026&mese=3")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agente Rossi")
        self.assertContains(response, "Provvigioni")
        self.assertContains(response, "OC-1")

    def test_pagina_con_parametri_non_validi(self):
        self.login()
        response = self.client.get(reverse("sales:commission_report") + "?anno=abc&mese=99&stato=strano")
        self.assertEqual(response.status_code, 200)

    def test_pagina_vuota_avvisa(self):
        self.login()
        response = self.client.get(reverse("sales:commission_report") + "?anno=2026&mese=3")
        self.assertContains(response, "Nessuna provvigione")

    def test_utente_senza_ruolo_non_accede(self):
        utente = User.objects.create_user("nessuno", password="password123!")
        self.login(utente)
        response = self.client.get(reverse("sales:commission_report"))
        self.assertEqual(response.status_code, 403)

    def test_ruolo_vendite_accede(self):
        vendite = User.objects.create_user("venditore", password="password123!")
        vendite.groups.add(Group.objects.get(name="Vendite"))
        self.login(vendite)
        response = self.client.get(reverse("sales:commission_report"))
        self.assertEqual(response.status_code, 200)
