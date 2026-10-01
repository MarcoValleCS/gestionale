"""Test di cantieri, manutenzioni programmate e seriali."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.sales.models import Quote, QuoteTemplate, QuoteTemplateLine

from .models import Asset, Job, MaintenancePlan

User = get_user_model()


class JobsTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.customer = Contact.objects.create(name="Rossi Piscine S.r.l.", is_customer=True)
        cls.product = Product.objects.create(
            name="Pompa di ricircolo",
            uom=cls.uom,
            sale_price=Decimal("450.00"),
            sale_vat=cls.vat,
            purchase_price=Decimal("280.00"),
            purchase_vat=cls.vat,
        )

    def login(self):
        self.client.force_login(self.user)


class JobTest(JobsTestBase):
    def test_crea_cantiere_tramite_vista(self):
        self.login()
        response = self.client.post(
            reverse("jobs:job_create"),
            {
                "name": "Piscina 8x4 – Via Verdi",
                "customer": self.customer.pk,
                "status": Job.STATUS_SURVEY,
                "address": "Via Verdi 12",
                "zip_code": "20100",
                "city": "Milano",
                "province": "MI",
                "manager": self.user.pk,
                "start_date": "2026-04-01",
                "end_date": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get()
        self.assertTrue(job.code.startswith("CAN"))
        self.assertEqual(job.customer, self.customer)
        self.assertTrue(job.is_open)

    def test_documenti_collegati_visibili_nel_cantiere(self):
        job = Job.objects.create(name="Piscina test", customer=self.customer)
        quote = Quote.objects.create(customer=self.customer, job=job)
        quote.lines.create(product=self.product, description="x", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("100"), vat_rate=self.vat)
        quote.recalculate()

        self.login()
        response = self.client.get(reverse("jobs:job_detail", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, quote.number)


class MaintenanceTest(JobsTestBase):
    def test_crea_manutenzione_e_avanzamento(self):
        plan = MaintenancePlan.objects.create(
            name="Manutenzione stagionale",
            customer=self.customer,
            frequency=MaintenancePlan.FREQUENCY_QUARTERLY,
            next_date=date(2026, 1, 15),
        )
        self.login()

        response = self.client.post(reverse("jobs:maintenance_advance", args=[plan.pk]))
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.next_date, date(2026, 4, 15))

    def test_avanzamento_fine_mese(self):
        plan = MaintenancePlan.objects.create(
            name="Canone mensile",
            customer=self.customer,
            frequency=MaintenancePlan.FREQUENCY_MONTHLY,
            next_date=date(2026, 1, 31),
        )
        plan.advance()
        self.assertEqual(plan.next_date, date(2026, 2, 28))

    def test_crea_preventivo_dal_modello(self):
        template = QuoteTemplate.objects.create(name="Manutenzione piscina", terms_text="Contratto annuale")
        QuoteTemplateLine.objects.create(
            template=template, position=1, product=self.product, description="Manutenzione", qty=Decimal("1"),
            uom=self.uom, unit_price=Decimal("350.00"), vat_rate=self.vat,
        )
        plan = MaintenancePlan.objects.create(
            name="Manutenzione annuale",
            customer=self.customer,
            template=template,
            next_date=timezone.localdate(),
        )
        self.login()

        response = self.client.post(reverse("jobs:maintenance_create_quote", args=[plan.pk]))
        quote = Quote.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(quote.customer, self.customer)
        self.assertEqual(quote.status, Quote.STATUS_DRAFT)
        self.assertEqual(quote.lines.count(), 1)
        self.assertEqual(quote.grand_total, Decimal("427.00"))  # 350 + 22%

    def test_manutenzione_in_scadenza_in_dashboard(self):
        MaintenancePlan.objects.create(
            name="Apertura piscina",
            customer=self.customer,
            next_date=timezone.localdate() + timedelta(days=5),
        )
        self.login()
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Apertura piscina")
        self.assertContains(response, "Manutenzioni in scadenza")


class AssetTest(JobsTestBase):
    def test_seriale_con_garanzia(self):
        job = Job.objects.create(name="Piscina seriali", customer=self.customer)
        self.login()
        response = self.client.post(
            reverse("jobs:asset_create"),
            {
                "product": self.product.pk,
                "serial_number": "POMPA-2026-001",
                "job": job.pk,
                "customer": "",
                "installed_on": "2026-05-10",
                "warranty_months": "24",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        asset = Asset.objects.get()
        self.assertEqual(asset.customer, self.customer)  # preso dal cantiere
        self.assertEqual(asset.warranty_until, date(2028, 5, 10))
        self.assertTrue(asset.under_warranty)

    def test_seriale_unico_per_articolo(self):
        Asset.objects.create(product=self.product, serial_number="X1")
        with self.assertRaises(Exception):
            Asset.objects.create(product=self.product, serial_number="X1")


class JobsPagesSmokeTest(JobsTestBase):
    def test_pagine(self):
        self.login()
        job = Job.objects.create(name="Cantiere smoke", customer=self.customer)
        plan = MaintenancePlan.objects.create(name="Manutenzione smoke", customer=self.customer)
        asset = Asset.objects.create(product=self.product, serial_number="SMOKE-1", job=job)

        urls = [
            reverse("jobs:job_list"),
            reverse("jobs:job_create"),
            reverse("jobs:job_detail", args=[job.pk]),
            reverse("jobs:job_update", args=[job.pk]),
            reverse("jobs:maintenance_list"),
            reverse("jobs:maintenance_create"),
            reverse("jobs:maintenance_update", args=[plan.pk]),
            reverse("jobs:asset_list"),
            reverse("jobs:asset_create"),
            reverse("jobs:asset_update", args=[asset.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"{url} → {response.status_code}")

    def test_filtri(self):
        self.login()
        urls = [
            reverse("jobs:job_list") + "?stato=aperti",
            reverse("jobs:maintenance_list") + "?stato=scadenza",
            reverse("jobs:asset_list") + "?garanzia=valida",
            reverse("jobs:asset_list") + "?q=SMOKE",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
