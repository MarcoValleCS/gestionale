"""Doppio invio: lo stesso passaggio di stato chiesto due volte.

È ciò che succede con un doppio clic o con due utenti sulla stessa scheda:
entrambe le richieste leggono il documento in bozza prima che l'altra salvi.
Si simula leggendo due copie dello stesso oggetto e passandole una dopo
l'altra al servizio: la seconda deve essere rifiutata e il magazzino toccato
una volta sola. L'ultimo test lo verifica anche con thread veri.
"""
import threading
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, TransactionTestCase

from apps.billing.models import DeliveryNote, SalesInvoice
from apps.billing.services import (
    create_delivery_note_from_order,
    create_sales_invoice_from_delivery_note,
    issue_delivery_note,
)
from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import UnitOfMeasure, VatRate
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import register_movement
from apps.purchasing.models import PurchaseOrder
from apps.purchasing.services import receive_purchase_order
from apps.sales.models import Quote, SalesOrder, SalesOrderLine
from apps.sales.services import _consegna_riga, confirm_sales_order, convert_quote_to_order, deliver_sales_order


class DoppioInvioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uom = UnitOfMeasure.objects.get(code="PZ")
        cls.vat22 = VatRate.objects.get(code="22")
        cls.customer = Contact.objects.create(name="Cliente Doppio Clic", is_customer=True)
        cls.supplier = Contact.objects.create(name="Fornitore Doppio Clic", is_supplier=True)
        cls.product = Product.objects.create(
            name="Raccordo", uom=cls.uom, sale_price=Decimal("10"), sale_vat=cls.vat22,
            purchase_price=Decimal("4"), purchase_vat=cls.vat22, main_supplier=cls.supplier,
        )
        register_movement(
            product=cls.product, delta=Decimal("100"), movement_type=StockMovement.TYPE_LOAD,
            warehouse=Warehouse.get_default(),
        )

    def _movimenti(self):
        return StockMovement.objects.filter(product=self.product).count()

    def _ordine(self, stato=SalesOrder.STATUS_DRAFT, qty="3"):
        ordine = SalesOrder.objects.create(customer=self.customer, status=stato)
        ordine.lines.create(
            product=self.product, description="Raccordo", qty=Decimal(qty), uom=self.uom,
            unit_price=Decimal("10"), vat_rate=self.vat22,
        )
        ordine.recalculate()
        return ordine

    def test_ddt_emesso_due_volte_scarica_una_volta(self):
        ordine = self._ordine(SalesOrder.STATUS_CONFIRMED)
        ddt = create_delivery_note_from_order(ordine)
        copia_a = DeliveryNote.objects.get(pk=ddt.pk)
        copia_b = DeliveryNote.objects.get(pk=ddt.pk)
        prima = self._movimenti()

        issue_delivery_note(copia_a)
        with self.assertRaises(ValidationError):
            issue_delivery_note(copia_b)

        self.assertEqual(self._movimenti(), prima + 1)
        self.assertEqual(ordine.lines.get().qty_delivered, Decimal("3"))
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, SalesOrder.STATUS_DELIVERED)

    def test_ddt_parziale_somma_le_quantita_consegnate(self):
        ordine = self._ordine(SalesOrder.STATUS_CONFIRMED, qty="5")
        primo = create_delivery_note_from_order(ordine)
        primo.lines.update(qty=Decimal("2"))
        issue_delivery_note(DeliveryNote.objects.get(pk=primo.pk))
        secondo = create_delivery_note_from_order(ordine)
        self.assertEqual(secondo.lines.get().qty, Decimal("3"))
        issue_delivery_note(DeliveryNote.objects.get(pk=secondo.pk))
        self.assertEqual(ordine.lines.get().qty_delivered, Decimal("5"))
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, SalesOrder.STATUS_DELIVERED)

    def test_ddt_fatturato_due_volte_crea_una_fattura(self):
        ddt = create_delivery_note_from_order(self._ordine(SalesOrder.STATUS_CONFIRMED))
        issue_delivery_note(ddt)
        copia_a = DeliveryNote.objects.get(pk=ddt.pk)
        copia_b = DeliveryNote.objects.get(pk=ddt.pk)

        create_sales_invoice_from_delivery_note(copia_a)
        with self.assertRaises(ValidationError):
            create_sales_invoice_from_delivery_note(copia_b)
        self.assertEqual(SalesInvoice.objects.filter(source_delivery_note=ddt).count(), 1)

    def test_conferma_due_volte_genera_gli_ordini_fornitore_una_volta(self):
        ordine = self._ordine(qty="500")  # più della giacenza: serve un ordine fornitore
        copia_a = SalesOrder.objects.get(pk=ordine.pk)
        copia_b = SalesOrder.objects.get(pk=ordine.pk)

        confirm_sales_order(copia_a)
        with self.assertRaises(ValidationError):
            confirm_sales_order(copia_b)
        self.assertEqual(PurchaseOrder.objects.filter(source_sales_order=ordine).count(), 1)
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, SalesOrder.STATUS_CONFIRMED)
        self.assertIsNotNone(ordine.confirmed_at)

    def test_conversione_due_volte_crea_un_ordine(self):
        preventivo = Quote.objects.create(customer=self.customer)
        preventivo.lines.create(
            product=self.product, description="Raccordo", qty=Decimal("1"), uom=self.uom,
            unit_price=Decimal("10"), vat_rate=self.vat22,
        )
        copia_a = Quote.objects.get(pk=preventivo.pk)
        copia_b = Quote.objects.get(pk=preventivo.pk)

        convert_quote_to_order(copia_a)
        with self.assertRaises(ValidationError):
            convert_quote_to_order(copia_b)
        self.assertEqual(SalesOrder.objects.filter(source_quote=preventivo).count(), 1)

    def test_il_passaggio_di_stato_finisce_nel_registro_attivita(self):
        from apps.core.models import ActivityLog

        ordine = self._ordine()
        confirm_sales_order(SalesOrder.objects.get(pk=ordine.pk))
        voce = ActivityLog.objects.filter(object_id=str(ordine.pk), action="modificato").latest("pk")
        self.assertIn("status", voce.details)

    def test_riga_consegnata_due_volte_scarica_una_volta(self):
        ordine = self._ordine(SalesOrder.STATUS_CONFIRMED)
        riga = ordine.lines.get()
        copia_a = SalesOrderLine.objects.select_related("product").get(pk=riga.pk)
        copia_b = SalesOrderLine.objects.select_related("product").get(pk=riga.pk)
        prima = self._movimenti()

        self.assertTrue(_consegna_riga(copia_a, None, None, ordine.number))
        self.assertFalse(_consegna_riga(copia_b, None, None, ordine.number))
        self.assertEqual(self._movimenti(), prima + 1)

    def test_consegna_senza_giacenza_lascia_la_riga_da_consegnare(self):
        ordine = self._ordine(SalesOrder.STATUS_CONFIRMED, qty="1000")
        errori = deliver_sales_order(SalesOrder.objects.get(pk=ordine.pk))
        self.assertEqual(len(errori), 1)
        riga = ordine.lines.get()
        self.assertEqual(riga.qty_delivered, Decimal("0"))
        self.assertIsNone(riga.unit_cost, "anche il costo resta da fissare alla vera consegna")
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, SalesOrder.STATUS_CONFIRMED)

    def test_ricezione_inviata_due_volte_carica_una_volta(self):
        ordine = PurchaseOrder.objects.create(supplier=self.supplier)
        riga = ordine.lines.create(
            product=self.product, description="Raccordo", qty=Decimal("5"), uom=self.uom,
            unit_price=Decimal("4"), vat_rate=self.vat22,
        )
        # La seconda richiesta ha letto le righe prima che la prima salvasse.
        copia_b = PurchaseOrder.objects.get(pk=ordine.pk)
        righe_lette_prima = list(copia_b.lines.select_related("product"))
        prima = self._movimenti()

        ricevute, errori = receive_purchase_order(PurchaseOrder.objects.get(pk=ordine.pk), {str(riga.pk): "5"})
        self.assertEqual((len(ricevute), errori), (1, []))

        with mock.patch("django.db.models.query.QuerySet.select_related", return_value=righe_lette_prima):
            ricevute, errori = receive_purchase_order(copia_b, {str(riga.pk): "5"})
        self.assertEqual(ricevute, [])
        self.assertEqual(len(errori), 1)
        self.assertEqual(self._movimenti(), prima + 1)
        riga.refresh_from_db()
        self.assertEqual(riga.qty_received, Decimal("5"))

    def test_ricezione_parziale_con_decimali(self):
        """Il confronto esatto non deve rifiutare ricezioni legittime con i decimali."""
        ordine = PurchaseOrder.objects.create(supplier=self.supplier)
        riga = ordine.lines.create(
            product=self.product, description="Tubo", qty=Decimal("0.3"), uom=self.uom,
            unit_price=Decimal("4"), vat_rate=self.vat22,
        )
        for quantita in ("0.1", "0.2"):
            with self.subTest(quantita=quantita):
                ricevute, errori = receive_purchase_order(
                    PurchaseOrder.objects.get(pk=ordine.pk), {str(riga.pk): quantita}
                )
                self.assertEqual(errori, [])
                self.assertEqual(len(ricevute), 1)
        riga.refresh_from_db()
        self.assertEqual(riga.qty_received, Decimal("0.3"))
        ordine.refresh_from_db()
        self.assertEqual(ordine.status, PurchaseOrder.STATUS_RECEIVED)


class EmissioneDdtContemporaneaTest(TransactionTestCase):
    """Tre thread che emettono lo stesso DDT nello stesso istante."""

    def test_un_solo_scarico(self):
        uom, _ = UnitOfMeasure.objects.get_or_create(code="PZ", defaults={"name": "Pezzi"})
        vat, _ = VatRate.objects.get_or_create(code="22", defaults={"name": "IVA 22%", "rate": Decimal("22")})
        if Warehouse.get_default() is None:
            Warehouse.objects.create(name="Magazzino di prova", code="PROVA", is_default=True)
        cliente = Contact.objects.create(name="Cliente Thread", is_customer=True)
        articolo = Product.objects.create(
            name="Valvola", uom=uom, sale_price=Decimal("10"), sale_vat=vat, purchase_vat=vat
        )
        register_movement(product=articolo, delta=Decimal("50"), movement_type=StockMovement.TYPE_LOAD)
        ordine = SalesOrder.objects.create(customer=cliente, status=SalesOrder.STATUS_CONFIRMED)
        ordine.lines.create(product=articolo, description="Valvola", qty=Decimal("2"), uom=uom, vat_rate=vat)
        ddt = create_delivery_note_from_order(ordine)

        quanti = 3
        barriera = threading.Barrier(quanti)
        esiti = []
        lucchetto = threading.Lock()

        def emetti():
            try:
                copia = DeliveryNote.objects.get(pk=ddt.pk)
                barriera.wait(timeout=15)
                issue_delivery_note(copia)
                esito = "ok"
            except ValidationError:
                esito = "rifiutato"
            except Exception as exc:  # noqa: BLE001 - vogliamo vedere qualsiasi errore
                esito = f"{type(exc).__name__}: {exc}"
            finally:
                connection.close()
            with lucchetto:
                esiti.append(esito)

        threads = [threading.Thread(target=emetti) for _ in range(quanti)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=45)

        self.assertEqual(sorted(esiti), ["ok"] + ["rifiutato"] * (quanti - 1), esiti)
        scarichi = StockMovement.objects.filter(product=articolo, movement_type=StockMovement.TYPE_UNLOAD)
        self.assertEqual(scarichi.count(), 1)
