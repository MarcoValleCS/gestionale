"""Test del flusso di vendita completo e delle pagine principali."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.contacts.models import Contact
from apps.core.models import CompanySettings, Tag, UnitOfMeasure, VatRate
from apps.inventory.models import StockLevel, Warehouse
from apps.inventory.services import register_movement
from apps.purchasing.models import PurchaseOrder, SupplierPriceList, PriceListItem
from apps.purchasing.services import apply_pricelist_adjustment

from . import analytics, services
from .models import Quote, SalesOrder

User = get_user_model()


class FlowTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat22 = VatRate.objects.get(code="22")
        cls.vat10 = VatRate.objects.get(code="10")
        cls.warehouse = Warehouse.get_default()

        cls.customer = Contact.objects.create(name="Cliente Test S.r.l.", is_customer=True, is_supplier=False, city="Milano")
        cls.supplier = Contact.objects.create(name="Fornitore Test S.p.A.", is_customer=False, is_supplier=True, city="Torino")

        cls.product = Product.objects.create(
            name="Bullone M8",
            uom=cls.uom,
            sale_price=Decimal("10.00"),
            sale_vat=cls.vat22,
            purchase_price=Decimal("5.00"),
            purchase_vat=cls.vat22,
            main_supplier=cls.supplier,
            min_stock=Decimal("20"),
        )

    def login(self):
        self.client.force_login(self.user)


class FullFlowTest(FlowTestBase):
    def test_preventivo_ordine_acquisti_consegna(self):
        self.login()

        # 1. Creazione preventivo tramite form web
        response = self.client.post(
            reverse("sales:quote_create"),
            {
                "customer": self.customer.pk,
                "date": "2026-01-10",
                "valid_until": "2026-02-10",
                "payment_term": "",
                "reference": "Rif cliente 1",
                "terms_text": "",
                "notes": "",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-product": self.product.pk,
                "lines-0-description": "",
                "lines-0-qty": "10",
                "lines-0-uom": self.uom.pk,
                "lines-0-unit_price": "10.00",
                "lines-0-discount_pct": "0",
                "lines-0-vat_rate": self.vat22.pk,
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        quote = Quote.objects.get()
        self.assertTrue(quote.number.startswith("PRE-"))
        self.assertEqual(quote.subtotal, Decimal("100.00"))
        self.assertEqual(quote.vat_total, Decimal("22.00"))
        self.assertEqual(quote.grand_total, Decimal("122.00"))
        line = quote.lines.get()
        self.assertEqual(line.description, "Bullone M8")  # riempita dall'articolo

        # 2. Invio e accettazione
        self.client.post(reverse("sales:quote_send", args=[quote.pk]))
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_SENT)

        self.client.post(reverse("sales:quote_accept", args=[quote.pk]))
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_ACCEPTED)

        # 3. Conversione in ordine cliente
        self.client.post(reverse("sales:quote_convert", args=[quote.pk]))
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_CONVERTED)
        order = SalesOrder.objects.get()
        self.assertTrue(order.number.startswith("OC-"))
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.lines.count(), 1)

        # 4. Conferma ordine → nessuna giacenza → ordine fornitore automatico
        self.client.post(reverse("sales:order_confirm", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_CONFIRMED)
        po = PurchaseOrder.objects.get()
        self.assertEqual(po.supplier, self.supplier)
        self.assertEqual(po.source_sales_order, order)
        po_line = po.lines.get()
        self.assertEqual(po_line.qty, Decimal("10"))
        self.assertEqual(po_line.unit_price, Decimal("5.00"))

        # 5. Ricezione merce → carico magazzino
        self.client.post(reverse("purchasing:po_receive", args=[po.pk]), {"receive_all": "1"})
        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.STATUS_RECEIVED)
        level = StockLevel.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(level.quantity, Decimal("10"))

        # 6. Consegna → scarico magazzino
        self.client.post(reverse("sales:order_deliver", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_DELIVERED)
        level.refresh_from_db()
        self.assertEqual(level.quantity, Decimal("0"))

    def test_conferma_senza_fornitore_non_crea_ordine(self):
        product_no_supplier = Product.objects.create(
            name="Articolo senza fornitore",
            uom=self.uom,
            sale_price=Decimal("3.00"),
            sale_vat=self.vat22,
            purchase_price=Decimal("1.00"),
            purchase_vat=self.vat22,
        )
        order = SalesOrder.objects.create(customer=self.customer)
        order.lines.create(product=product_no_supplier, description="x", qty=Decimal("2"), uom=self.uom, unit_price=Decimal("3"), vat_rate=self.vat22)
        order.recalculate()

        result = services.confirm_sales_order(order, user=self.user)
        self.assertEqual(len(result["purchase_orders"]), 0)
        self.assertEqual(len(result["without_supplier"]), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_CONFIRMED)

    def test_consegna_bloccata_senza_giacenza(self):
        order = SalesOrder.objects.create(customer=self.customer)
        order.lines.create(product=self.product, description="x", qty=Decimal("5"), uom=self.uom, unit_price=Decimal("10"), vat_rate=self.vat22)
        order.recalculate()
        services.confirm_sales_order(order, user=self.user)

        errors = services.deliver_sales_order(order, user=self.user)
        self.assertEqual(len(errors), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.STATUS_CONFIRMED)
        self.assertFalse(StockLevel.objects.filter(product=self.product).exists())

    def test_duplicazione_preventivo(self):
        quote = Quote.objects.create(customer=self.customer)
        quote.lines.create(product=self.product, description="x", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("10"), vat_rate=self.vat22)
        quote.recalculate()
        new_quote = services.duplicate_quote(quote, user=self.user)
        self.assertNotEqual(new_quote.pk, quote.pk)
        self.assertEqual(new_quote.status, Quote.STATUS_DRAFT)
        self.assertEqual(new_quote.grand_total, quote.grand_total)
        self.assertEqual(new_quote.lines.count(), 1)


class AnalyticsTest(FlowTestBase):
    def _delivered_order(self, qty="10", price="10.00", unit_cost="4.00"):
        order = SalesOrder.objects.create(
            customer=self.customer,
            status=SalesOrder.STATUS_DELIVERED,
            delivered_at=timezone.now(),
        )
        order.lines.create(
            product=self.product,
            description=self.product.name,
            qty=Decimal(qty),
            uom=self.uom,
            unit_price=Decimal(price),
            vat_rate=self.vat22,
            qty_delivered=Decimal(qty),
            unit_cost=Decimal(unit_cost) if unit_cost is not None else None,
        )
        order.recalculate()
        return order

    def test_fatturato_e_margine(self):
        self._delivered_order()

        summary = analytics.summary(analytics.PERIOD_YEAR)
        self.assertEqual(summary["revenue"], Decimal("100.00"))
        self.assertEqual(summary["cost"], Decimal("40.00"))
        self.assertEqual(summary["margin"], Decimal("60.00"))
        self.assertEqual(summary["margin_pct"], Decimal("60.00"))
        self.assertEqual(summary["orders"], 1)

        by_product = analytics.by_product(analytics.PERIOD_YEAR)
        self.assertEqual(len(by_product), 1)
        self.assertEqual(by_product[0]["label"], "Bullone M8")
        self.assertEqual(by_product[0]["margin"], Decimal("60.00"))

        by_supplier = analytics.by_supplier(analytics.PERIOD_YEAR)
        self.assertEqual(by_supplier[0]["label"], "Fornitore Test S.p.A.")
        self.assertEqual(by_supplier[0]["margin"], Decimal("60.00"))

    def test_margine_usa_prezzo_acquisto_se_costo_non_fissato(self):
        self._delivered_order(unit_cost=None)
        summary = analytics.summary(analytics.PERIOD_YEAR)
        # prezzo di acquisto dell'articolo = 5.00 → costo 50
        self.assertEqual(summary["cost"], Decimal("50.00"))
        self.assertEqual(summary["margin"], Decimal("50.00"))

    def test_serie_mensile(self):
        self._delivered_order()
        series = analytics.monthly_series(12)
        self.assertEqual(len(series["labels"]), 12)
        self.assertEqual(series["revenue"][-1], 100.0)
        self.assertEqual(series["margin"][-1], 60.0)
        self.assertEqual(series["revenue"][0], 0.0)

    def test_ordini_non_consegnati_esclusi(self):
        order = SalesOrder.objects.create(customer=self.customer, status=SalesOrder.STATUS_CONFIRMED)
        order.lines.create(product=self.product, description="x", qty=Decimal("5"), uom=self.uom, unit_price=Decimal("10"), vat_rate=self.vat22)
        order.recalculate()
        summary = analytics.summary(analytics.PERIOD_YEAR)
        self.assertEqual(summary["revenue"], Decimal("0"))

    def test_dashboard_con_statistiche(self):
        self._delivered_order()
        self.login()
        for period in ("anno", "mese", "12m"):
            with self.subTest(period=period):
                response = self.client.get(reverse("core:home") + f"?periodo={period}")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Marginalità per articolo")


class VatAndTotalsTest(FlowTestBase):
    def test_totali_con_iva_mista_e_sconto(self):
        quote = Quote.objects.create(customer=self.customer)
        quote.lines.create(product=self.product, description="a", qty=Decimal("2"), uom=self.uom, unit_price=Decimal("10"), discount_pct=Decimal("10"), vat_rate=self.vat22)
        quote.lines.create(product=self.product, description="b", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("100"), vat_rate=self.vat10)
        quote.recalculate()

        # Riga 1: 2*10*0.9 = 18 → IVA 22% = 3.96
        # Riga 2: 100 → IVA 10% = 10.00
        self.assertEqual(quote.subtotal, Decimal("118.00"))
        self.assertEqual(quote.vat_total, Decimal("13.96"))
        self.assertEqual(quote.grand_total, Decimal("131.96"))

        rows = quote.vat_breakdown()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["rate"].code, "22")
        self.assertEqual(rows[0]["base"], Decimal("18.00"))
        self.assertEqual(rows[0]["vat"], Decimal("3.96"))
        self.assertEqual(rows[1]["rate"].code, "10")


class PriceListTest(FlowTestBase):
    def test_adeguamento_percentuale_listino(self):
        pricelist = SupplierPriceList.objects.create(supplier=self.supplier, name="Listino 2026")
        item = PriceListItem.objects.create(pricelist=pricelist, product=self.product, price=Decimal("10.00"))

        apply_pricelist_adjustment(pricelist, Decimal("3"), user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("10.30"))
        self.assertEqual(pricelist.adjustments.count(), 1)
        self.assertEqual(pricelist.adjustments.first().items_count, 1)

    def test_prezzo_acquisto_da_listino(self):
        pricelist = SupplierPriceList.objects.create(supplier=self.supplier, name="Listino attivo")
        PriceListItem.objects.create(pricelist=pricelist, product=self.product, price=Decimal("4.00"), discount_pct=Decimal("10"))
        # Prezzo effettivo: 3.60; il prezzo articolo è 5.00 → vince il listino
        self.assertEqual(self.product.purchase_unit_price(self.supplier), Decimal("3.6000"))


class PagesSmokeTest(FlowTestBase):
    """Verifica che le pagine principali rispondano senza errori."""

    def setUp(self):
        self.login()

    def test_pagine_principali(self):
        quote = Quote.objects.create(customer=self.customer)
        quote.lines.create(product=self.product, description="x", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("10"), vat_rate=self.vat22)
        quote.recalculate()
        order = SalesOrder.objects.create(customer=self.customer)
        order.lines.create(product=self.product, description="x", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("10"), vat_rate=self.vat22)
        order.recalculate()
        po = PurchaseOrder.objects.create(supplier=self.supplier)
        po.lines.create(product=self.product, description="x", qty=Decimal("1"), uom=self.uom, unit_price=Decimal("5"), vat_rate=self.vat22)
        po.recalculate()
        pricelist = SupplierPriceList.objects.create(supplier=self.supplier, name="Listino smoke")
        PriceListItem.objects.create(pricelist=pricelist, product=self.product, price=Decimal("5.00"))
        register_movement(product=self.product, delta=Decimal("5"), movement_type="load", user=self.user)

        urls = [
            reverse("core:home"),
            reverse("core:settings"),
            reverse("core:company_update"),
            reverse("core:vat_list"),
            reverse("core:vat_create"),
            reverse("core:uom_list"),
            reverse("core:tag_list"),
            reverse("core:paymentterm_list"),
            reverse("core:sequence_list"),
            reverse("accounts:user_list"),
            reverse("accounts:user_create"),
            reverse("accounts:password_change"),
            reverse("contacts:list"),
            reverse("contacts:create"),
            reverse("contacts:detail", args=[self.customer.pk]),
            reverse("contacts:update", args=[self.customer.pk]),
            reverse("catalog:product_list"),
            reverse("catalog:product_create"),
            reverse("catalog:product_import"),
            reverse("catalog:product_import_template"),
            reverse("catalog:product_detail", args=[self.product.pk]),
            reverse("catalog:product_update", args=[self.product.pk]),
            reverse("catalog:category_list"),
            reverse("inventory:stock_list"),
            reverse("inventory:movement_list"),
            reverse("inventory:adjust_create"),
            reverse("sales:quote_list"),
            reverse("sales:quote_create"),
            reverse("sales:quote_detail", args=[quote.pk]),
            reverse("sales:quote_update", args=[quote.pk]),
            reverse("sales:quote_print", args=[quote.pk]),
            reverse("sales:order_list"),
            reverse("sales:order_create"),
            reverse("sales:order_detail", args=[order.pk]),
            reverse("sales:order_update", args=[order.pk]),
            reverse("sales:order_print", args=[order.pk]),
            reverse("purchasing:po_list"),
            reverse("purchasing:po_create"),
            reverse("purchasing:po_detail", args=[po.pk]),
            reverse("purchasing:po_update", args=[po.pk]),
            reverse("purchasing:po_print", args=[po.pk]),
            reverse("purchasing:po_receive", args=[po.pk]),
            reverse("purchasing:pricelist_list"),
            reverse("purchasing:pricelist_create"),
            reverse("purchasing:pricelist_detail", args=[pricelist.pk]),
            reverse("purchasing:pricelist_update", args=[pricelist.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"{url} → {response.status_code}")

    def test_ricerca_drilldown(self):
        urls = [
            reverse("contacts:list") + "?q=Cliente&tipo=clienti",
            reverse("catalog:product_list") + "?sotto_scorta=1",
            reverse("inventory:stock_list") + "?sotto_scorta=1",
            reverse("sales:quote_list") + "?stato=aperti",
            reverse("sales:order_list") + "?stato=aperti",
            reverse("purchasing:po_list") + "?stato=aperti",
            reverse("purchasing:pricelist_list") + "?inattivi=1",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)


class PermissionsTest(FlowTestBase):
    def test_anonimo_rediretto_al_login(self):
        urls = [
            reverse("core:home"),
            reverse("contacts:list"),
            reverse("catalog:product_list"),
            reverse("sales:quote_list"),
            reverse("inventory:stock_list"),
            reverse("catalog:product_defaults", args=[self.product.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)

    def test_utente_senza_ruolo_non_accede(self):
        from django.contrib.auth.models import Group

        user = User.objects.create_user("mario", password="password123!")
        user.groups.add(Group.objects.get(name="Vendite"))
        self.client.force_login(user)

        # I preventivi sono accessibili al ruolo Vendite
        self.assertEqual(self.client.get(reverse("sales:quote_list")).status_code, 200)
        # Le impostazioni no
        self.assertEqual(self.client.get(reverse("core:settings")).status_code, 403)
        # Gli utenti no
        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 403)
        # I listini no
        self.assertEqual(self.client.get(reverse("purchasing:pricelist_list")).status_code, 403)
