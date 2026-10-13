"""Test dell'importazione da Odoo (comando ``importa_odoo``).

Il dump di prova è minimo ma completo: due contatti, due articoli, un
preventivo, un ordine cliente e un ordine fornitore con reverse charge, una
fattura e una giacenza. Serve a proteggere il parser COPY e le mappature
(codici, aliquote effettive, stati) da regressioni.
"""
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from apps.billing.models import SalesInvoice
from apps.catalog.models import Category, Product
from apps.contacts.models import Contact
from apps.inventory.models import StockLevel
from apps.purchasing.models import PriceListItem, PurchaseOrder
from apps.sales.models import Quote, SalesOrder

INT = "\\N"


def _dump(tabelle):
    """Costruisce un dump in formato pg_dump plain dalle tabelle indicate."""
    parti = []
    for nome, (colonne, righe) in tabelle.items():
        parti.append(f"COPY public.{nome} ({', '.join(colonne)}) FROM stdin;")
        for riga in righe:
            parti.append("\t".join(riga))
        parti.append("\\.")
    return "\n".join(parti) + "\n"


TABELLE = {
    "res_partner": (
        ["id", "name", "active", "is_company", "type", "parent_id", "vat",
         "l10n_it_codice_fiscale", "l10n_it_pa_index", "l10n_it_pec_email",
         "email", "phone", "website", "street", "street2", "zip", "city",
         "state_id", "country_id", "comment", "customer_rank", "supplier_rank",
         "property_payment_term_id", "property_supplier_payment_term_id"],
        [
            ["1", "ROSSIMOBILI SRL", "t", "t", "contact", INT, "IT01234567890",
             "01234567890", "SUBM70N", "pec@rossimobili.it", "info@rossimobili.it",
             "035123456", "www.rossimobili.it", "Via Roma 1", INT, "24000",
             "Bergamo", "1", "1", "<p>Cliente storico</p>", "1", "0", "1", INT],
            ["2", "FORNITORE UNO SPA", "t", "t", "contact", INT, "IT09876543210",
             INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, "1", INT,
             "0", "1", INT, "1"],
        ],
    ),
    "res_country": (["id", "name"], [["1", "Italia"]]),
    "res_country_state": (["id", "code"], [["1", "BG"]]),
    "uom_uom": (["id", "name", "active"], [["1", '{"it_IT": "Unità"}', "t"]]),
    "account_tax": (
        ["id", "name", "amount", "type_tax_use", "active"],
        [
            ["1", '{"it_IT": "22%"}', "22.0000", "sale", "t"],
            ["2", '{"it_IT": "22% M IC"}', "22.0000", "purchase", "t"],
        ],
    ),
    "account_tax_repartition_line": (
        ["id", "tax_id", "repartition_type", "document_type", "factor_percent"],
        [
            ["1", "1", "base", "invoice", "100.0"],
            ["2", "1", "tax", "invoice", "100.0"],
            ["3", "2", "base", "invoice", "100.0"],
            ["4", "2", "tax", "invoice", "100.0"],
            ["5", "2", "tax", "invoice", "-100.0"],
        ],
    ),
    "account_payment_term": (["id", "name", "active"], [["1", '{"it_IT": "30 giorni"}', "t"]]),
    "product_category": (
        ["id", "name", "parent_id"],
        [["1", '{"it_IT": "Arredo bagno"}', INT]],
    ),
    "product_template": (
        ["id", "categ_id", "uom_id", "type", "is_storable", "default_code",
         "name", "description_sale", "description", "list_price", "active"],
        [
            ["10", "1", "1", "consu", "t", "MOB80", '{"it_IT": "Mobile bagno 80"}',
             "Mobile sospeso 80 cm", INT, "450.0", "t"],
            ["11", "1", "1", "consu", "t", INT, '{"it_IT": "Specchio senza codice"}',
             INT, INT, "0.0", "t"],
        ],
    ),
    "product_product": (
        ["id", "product_tmpl_id", "default_code", "barcode", "active"],
        [
            ["100", "10", "MOB80", "8001234567890", "t"],
            ["101", "11", INT, INT, "t"],
        ],
    ),
    "product_supplierinfo": (
        ["id", "partner_id", "product_tmpl_id", "price", "discount", "min_qty",
         "delay", "sequence", "product_code", "product_name"],
        [["1", "2", "10", "300.0", "0.00", "1.00", "3", "1", "FOR-MOB80", INT]],
    ),
    "product_pricelist_item": (
        ["id", "pricelist_id", "product_tmpl_id", "product_id"],
        [["1", "1", "11", INT]],
    ),
    "sale_order": (
        ["id", "name", "state", "partner_id", "payment_term_id", "client_order_ref",
         "origin", "note", "validity_date", "date_order", "delivery_status",
         "invoice_status", "commitment_date", "amount_total", "amount_untaxed"],
        [
            ["1", "PREV0001", "sale", "1", "1", "RIF-1", INT,
             "<div>Consegna al piano</div>", "2026-05-01", "2026-04-01 10:00:00",
             "full", "invoiced", "2026-04-20", "610.00", "500.00"],
            ["2", "PREV0002", "draft", "1", INT, INT, INT, INT, INT,
             "2026-04-02 10:00:00", INT, "no", INT, "100.00", "100.00"],
        ],
    ),
    "sale_order_line": (
        ["id", "order_id", "sequence", "product_id", "product_uom_id", "display_type",
         "name", "product_uom_qty", "price_unit", "discount", "price_subtotal",
         "qty_delivered", "purchase_price"],
        [
            ["1", "1", "1", "100", "1", INT, "[MOB80] Mobile sospeso 80", "1.00",
             "500.0", "0.00", "500.00", "1.00", "300.0"],
            ["2", "1", "2", INT, INT, "line_note", "Nota libera", "0.00", "0.0",
             "0.00", "0.00", "0.00", "0.0"],
            ["3", "2", "1", INT, INT, INT, "Voce a corpo", "1.00", "100.0",
             "0.00", "100.00", "0.00", "0.0"],
            ["4", "1", "3", "101", "1", INT, "Specchio senza codice", "1.00",
             "0.0", "0.00", "0.00", "0.00", "0.0"],
        ],
    ),
    "account_tax_sale_order_line_rel": (
        ["sale_order_line_id", "account_tax_id"],
        [["1", "1"]],
    ),
    "purchase_order": (
        ["id", "name", "state", "partner_id", "payment_term_id", "partner_ref",
         "origin", "note", "date_order", "date_planned", "receipt_status",
         "amount_total", "amount_untaxed"],
        [["1", "PO001", "purchase", "2", "1", "RIF-F", INT, INT,
          "2026-04-05 10:00:00", "2026-04-15", "full", "200.00", "200.00"]],
    ),
    "purchase_order_line": (
        ["id", "order_id", "sequence", "uom_id", "product_id", "display_type",
         "name", "product_qty", "price_unit", "discount", "price_subtotal",
         "qty_received"],
        [["1", "1", "1", "1", "100", INT, "[FOR-MOB80] mobile da fornitore",
          "2.00", "100.0", "0.00", "200.00", "2.00"]],
    ),
    "account_tax_purchase_order_line_rel": (
        ["purchase_order_line_id", "account_tax_id"],
        [["1", "2"]],
    ),
    "account_move": (
        ["id", "name", "move_type", "state", "payment_state", "partner_id",
         "invoice_payment_term_id", "ref", "invoice_origin", "invoice_date",
         "date", "invoice_date_due", "narration", "amount_total", "amount_untaxed"],
        [["1", "FATT/2026/00001", "out_invoice", "posted", "paid", "1", "1",
          "RIF-FATT", "PREV0001", "2026-04-10", "2026-04-10", "2026-05-10",
          INT, "610.00", "500.00"]],
    ),
    "account_move_line": (
        ["id", "move_id", "sequence", "product_id", "product_uom_id", "display_type",
         "name", "quantity", "price_unit", "discount", "price_subtotal"],
        [["1", "1", "1", "100", "1", "product", "[MOB80] Mobile sospeso 80",
          "1.00", "500.0", "0.00", "500.00"]],
    ),
    "account_move_line_account_tax_rel": (
        ["account_move_line_id", "account_tax_id"],
        [["1", "1"]],
    ),
    "stock_quant": (
        ["product_id", "location_id", "quantity"],
        [["100", "5", "3.000"]],
    ),
    "stock_location": (
        ["id", "complete_name", "usage", "active"],
        [["5", "WH/Giacenza", "internal", "t"]],
    ),
}


class ImportaOdooTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.percorso = os.path.join(tempfile.mkdtemp(prefix="odoo-test-"), "dump.sql")
        with open(cls.percorso, "w", encoding="utf-8") as f:
            f.write(_dump(TABELLE))

    def _importa(self, *extra):
        call_command("importa_odoo", self.percorso, *extra, verbosity=0)

    def test_anteprima_non_scrive_nulla(self):
        self._importa()
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Contact.objects.count(), 0)

    def test_import_completo(self):
        self._importa("--conferma")

        # Contatti: P.IVA senza prefisso IT, provincia e condizioni di pagamento.
        cliente = Contact.objects.get(name="ROSSIMOBILI SRL")
        self.assertTrue(cliente.is_customer)
        self.assertFalse(cliente.is_supplier)
        self.assertEqual(cliente.vat_number, "01234567890")
        self.assertEqual(cliente.sdi_code, "SUBM70N")
        self.assertEqual(cliente.province, "BG")
        self.assertEqual(cliente.city, "Bergamo")
        self.assertEqual(cliente.payment_term.name, "30 giorni")
        self.assertEqual(cliente.notes, "Cliente storico")
        fornitore = Contact.objects.get(name="FORNITORE UNO SPA")
        self.assertTrue(fornitore.is_supplier)

        # Articoli: codice Odoo mantenuto, articolo senza codice rinumerato ART.
        mobile = Product.objects.get(code="MOB80")
        self.assertEqual(mobile.name, "Mobile bagno 80")
        self.assertEqual(mobile.category.name, "Arredo bagno")
        self.assertEqual(mobile.uom.code, "PZ")
        self.assertEqual(str(mobile.sale_price), "450.0000")
        self.assertEqual(mobile.main_supplier, fornitore)
        self.assertEqual(mobile.supplier_lead_days, 3)
        specchio = Product.objects.get(category__name="Arredo bagno", pk__gt=mobile.pk)
        self.assertTrue(specchio.code.startswith("ART"))
        self.assertEqual(Category.objects.count(), 1)

        # Listino fornitore.
        voce = PriceListItem.objects.get(product=mobile)
        self.assertEqual(str(voce.price), "300.0000")
        self.assertEqual(voce.supplier_code, "FOR-MOB80")
        self.assertEqual(voce.pricelist.supplier, fornitore)

        # Ordine cliente consegnato con totale IVA inclusa calcolato dalle righe.
        ordine = SalesOrder.objects.get(number="PREV0001")
        self.assertEqual(ordine.status, SalesOrder.STATUS_DELIVERED)
        self.assertIsNotNone(ordine.delivered_at)
        self.assertEqual(ordine.subtotal, 500)
        self.assertEqual(ordine.vat_total, 110)
        self.assertEqual(ordine.grand_total, 610)
        riga = ordine.lines.get(product=mobile)
        self.assertEqual(riga.description, "Mobile sospeso 80")
        self.assertEqual(riga.vat_rate.code, "22")
        self.assertEqual(riga.qty_delivered, 1)
        self.assertEqual(riga.unit_cost, 300)
        nota = ordine.lines.get(line_type="note")
        self.assertEqual(nota.description, "Nota libera")

        # Preventivo in bozza, riga senza imposta: niente IVA.
        preventivo = Quote.objects.get(number="PREV0002")
        self.assertEqual(preventivo.status, Quote.STATUS_DRAFT)
        self.assertEqual(preventivo.subtotal, 100)
        self.assertEqual(preventivo.vat_total, 0)
        self.assertEqual(preventivo.lines.first().vat_rate.code, "0")

        # Ordine fornitore con reverse charge: aliquota senza effetto sui totali.
        po = PurchaseOrder.objects.get(number="PO001")
        self.assertEqual(po.status, PurchaseOrder.STATUS_RECEIVED)
        riga_po = po.lines.get()
        self.assertEqual(riga_po.vat_rate.code, "N6")
        self.assertEqual(po.vat_total, 0)
        self.assertEqual(po.grand_total, 200)
        self.assertIn("Rif. fornitore: RIF-F", po.notes)

        # Fattura emessa, collegata all'ordine di partenza.
        fattura = SalesInvoice.objects.get(number="FATT/2026/00001")
        self.assertEqual(fattura.status, SalesInvoice.STATUS_PAID)
        self.assertEqual(fattura.source_order, ordine)
        self.assertEqual(fattura.grand_total, 610)

        # Giacenza del magazzino interno.
        livello = StockLevel.objects.get(product=mobile)
        self.assertEqual(livello.quantity, 3)

    def test_seconda_esecuzione_svuota_e_reimporta(self):
        self._importa("--conferma")
        self._importa("--conferma")
        self.assertEqual(Contact.objects.count(), 2)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(SalesOrder.objects.count(), 1)
        self.assertEqual(Quote.objects.count(), 1)
        self.assertEqual(PriceListItem.objects.count(), 1)
