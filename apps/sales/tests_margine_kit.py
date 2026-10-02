"""Test del margine nel preventivo e della gestione dei kit a magazzino."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement

from . import services
from .models import Quote, SalesOrder

Utente = get_user_model()


class KitTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Utente.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.pz = UnitOfMeasure.objects.get(code="PZ")
        cls.vat = VatRate.objects.get(code="22")
        cls.cliente = Contact.objects.create(name="Cliente Kit", is_customer=True)
        cls.fornitore = Contact.objects.create(name="Fornitore Kit", is_customer=False, is_supplier=True)

        def prodotto(codice, nome, prezzo, costo, tracciato=True, kit=False):
            return Product.objects.create(
                code=codice, name=nome, uom=cls.pz, sale_price=Decimal(prezzo),
                sale_vat=cls.vat, purchase_price=Decimal(costo), purchase_vat=cls.vat,
                main_supplier=cls.fornitore, is_stock_tracked=tracciato, is_kit=kit,
            )

        cls.vaso = prodotto("VASO", "Vaso sospeso", "300", "180")
        cls.bidet = prodotto("BIDET", "Bidet sospeso", "280", "170")
        cls.sedile = prodotto("SEDILE", "Sedile soft close", "90", "50")
        cls.kit = prodotto("KIT.BAGNO", "Kit bagno completo", "620", "0", tracciato=True, kit=True)

        from apps.catalog.models import KitComponent

        KitComponent.objects.create(kit=cls.kit, component=cls.vaso, qty=Decimal("1"))
        KitComponent.objects.create(kit=cls.kit, component=cls.bidet, qty=Decimal("1"))
        KitComponent.objects.create(kit=cls.kit, component=cls.sedile, qty=Decimal("1"))

        for articolo, quantita in ((cls.vaso, "10"), (cls.bidet, "10"), (cls.sedile, "10")):
            register_movement(
                product=articolo, delta=Decimal(quantita), movement_type=StockMovement.TYPE_LOAD,
                note="Carico iniziale",
            )

        cls.quote = Quote.objects.create(customer=cls.cliente)
        cls.quote.lines.create(
            product=cls.kit, description="Kit bagno completo", qty=Decimal("2"),
            uom=cls.pz, unit_price=Decimal("620"), vat_rate=cls.vat,
        )
        cls.quote.recalculate()

    def login(self):
        self.client.force_login(self.user)


class KitNonTracciatoTest(KitTestBase):
    def test_un_kit_non_e_gestito_a_magazzino(self):
        self.kit.refresh_from_db()
        self.assertFalse(self.kit.is_stock_tracked)

    def test_un_kit_non_compare_fra_gli_articoli_sotto_scorta(self):
        self.kit.min_stock = Decimal("5")
        self.kit.save()
        self.assertFalse(self.kit.is_low_stock)


class EspansioneKitTest(KitTestBase):
    def test_i_componenti_vengono_aggiunti_al_preventivo(self):
        nuove = services.espandi_kit(self.quote, "quote")
        self.assertEqual(len(nuove), 3)
        righe = list(self.quote.lines.order_by("position"))
        self.assertEqual(len(righe), 4)
        componenti = {riga.product.code: riga for riga in righe if riga.product_id in (self.vaso.pk, self.bidet.pk, self.sedile.pk)}
        self.assertEqual(set(componenti), {"VASO", "BIDET", "SEDILE"})
        for riga in componenti.values():
            self.assertEqual(riga.qty, Decimal("2"))       # 2 kit × 1 componente
            self.assertEqual(riga.unit_price, Decimal("0"))  # il prezzo resta sul kit
        # il totale non cambia: i componenti sono a prezzo zero
        self.assertEqual(self.quote.subtotal, Decimal("1240.00"))

    def test_espandere_due_volte_non_duplica(self):
        services.espandi_kit(self.quote, "quote")
        services.espandi_kit(self.quote, "quote")
        self.assertEqual(self.quote.lines.count(), 4)

    def test_preventivo_senza_kit_non_cambia(self):
        quote = Quote.objects.create(customer=self.cliente)
        quote.lines.create(product=self.vaso, description="Vaso", qty=Decimal("1"), uom=self.pz, unit_price=Decimal("300"), vat_rate=self.vat)
        quote.recalculate()
        self.assertEqual(services.espandi_kit(quote, "quote"), [])
        self.assertEqual(quote.lines.count(), 1)

    def test_espansione_al_salvataggio_dal_modulo(self):
        self.login()
        response = self.client.post(
            reverse("sales:quote_create"),
            {
                "customer": self.cliente.pk,
                "date": "2026-10-02",
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
                "lines-0-product": self.kit.pk,
                "lines-0-description": "Kit bagno",
                "lines-0-section": "",
                "lines-0-qty": "1",
                "lines-0-uom": self.pz.pk,
                "lines-0-unit_price": "620",
                "lines-0-discount_pct": "0",
                "lines-0-vat_rate": self.vat.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        nuovo = Quote.objects.exclude(pk=self.quote.pk).get()
        codici = set(nuovo.lines.values_list("product__code", flat=True))
        self.assertIn("VASO", codici)
        self.assertIn("BIDET", codici)


class ConsegnaConKitTest(KitTestBase):
    def test_la_consegna_scarica_i_componenti_non_il_kit(self):
        services.espandi_kit(self.quote, "quote")
        ordine = services.convert_quote_to_order(self.quote)
        services.espandi_kit(ordine, "order")
        ordine.status = SalesOrder.STATUS_CONFIRMED
        ordine.save(update_fields=["status"])

        errori = services.deliver_sales_order(ordine)
        self.assertEqual(errori, [])

        self.vaso.refresh_from_db()
        self.bidet.refresh_from_db()
        self.sedile.refresh_from_db()
        self.kit.refresh_from_db()
        self.assertEqual(self.vaso.total_stock, Decimal("8"))    # 10 - 2
        self.assertEqual(self.bidet.total_stock, Decimal("8"))
        self.assertEqual(self.sedile.total_stock, Decimal("8"))
        self.assertEqual(self.kit.total_stock, Decimal("0"))     # il kit non si scarica

    def test_senza_espansione_il_kit_non_scarica_nulla(self):
        """Se i componenti non ci sono, il magazzino resta com'era (non va in negativo)."""
        ordine = services.convert_quote_to_order(self.quote)
        ordine.status = SalesOrder.STATUS_CONFIRMED
        ordine.save(update_fields=["status"])
        errori = services.deliver_sales_order(ordine)
        self.assertEqual(errori, [])
        self.vaso.refresh_from_db()
        self.assertEqual(self.vaso.total_stock, Decimal("10"))


class MargineNelModuloTest(KitTestBase):
    def test_il_modulo_mostra_margine_e_costi(self):
        self.login()
        response = self.client.get(reverse("sales:quote_create"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Margine del preventivo", html)
        self.assertIn('id="product-costs"', html)
        self.assertIn("Costo merce", html)
        self.assertIn("Marginalità", html)
        # il costo del vaso è nel dizionario passato alla pagina
        self.assertIn(f'"{self.vaso.pk}": "180.0000"', html)

    def test_il_modulo_ordine_mostra_il_margine(self):
        self.login()
        response = self.client.get(reverse("sales:order_create"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Margine dell'ordine", response.content.decode())

    def test_la_riga_esistente_porta_il_costo_fissato(self):
        self.login()
        response = self.client.get(reverse("sales:quote_update", args=[self.quote.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("line-margin", response.content.decode())

