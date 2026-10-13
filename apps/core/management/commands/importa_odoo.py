"""Importa contatti, articoli, listini e documenti dal dump SQL di Odoo.

Uso:

    python manage.py importa_odoo C:\\percorso\\dump.sql          # anteprima
    python manage.py importa_odoo /tmp/dump.sql --conferma       # import vero

Senza ``--conferma`` il comando legge il dump e mostra solo l'anteprima di
quello che importerebbe, senza scrivere nulla. Con ``--conferma`` svuota i
dati di dominio (contatti, articoli, listini, preventivi, ordini, fatture,
giacenze, cantieri, lead, personale, galleria) e ricostruisce tutto dal dump
dentro un'unica transazione: se qualcosa va storto non resta un database a
metà.

Non vengono toccati utenti, gruppi, dati azienda, aliquote IVA, unità di
misura, condizioni di pagamento, numerazioni, fasi lead e il magazzino
predefinito: le voci già presenti vengono riusate e completate con quelle
mancanti.

Cosa entra: schede cliente/fornitore con indirizzi e condizioni di pagamento;
articoli usati nei documenti o presenti nei listini fornitori; listini
fornitori completi; preventivi, ordini cliente, ordini fornitore e fatture
emesse con righe, sezioni e sconti; giacenze del magazzino interno.
"""
import html
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from email.utils import getaddresses

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.contacts.models import Contact
from apps.core.models import NumberSequence, PaymentTerm, UnitOfMeasure, VatRate
from apps.core.rounding import round2
from apps.inventory.models import StockLevel, Warehouse
from apps.purchasing.models import PriceListItem, PurchaseOrder, PurchaseOrderLine, SupplierPriceList
from apps.sales.models import (
    LINE_ARTICLE,
    LINE_NOTE,
    LINE_SECTION,
    LINE_SUBSECTION,
    Quote,
    QuoteLine,
    SalesOrder,
    SalesOrderLine,
)

# Tabelle del dump che ci interessano, con le sole colonne che usiamo (i dump
# di Odoo hanno centinaia di colonne per tabella e decine di migliaia di righe:
# tenere tutto in memoria sarebbe uno spreco).
TABELLE = {
    "res_partner": (
        "id", "name", "active", "is_company", "type", "parent_id", "vat",
        "l10n_it_codice_fiscale", "l10n_it_pa_index", "l10n_it_pec_email",
        "email", "phone", "website", "street", "street2", "zip", "city",
        "state_id", "country_id", "comment", "customer_rank", "supplier_rank",
        "property_payment_term_id", "property_supplier_payment_term_id",
    ),
    "res_country": ("id", "name"),
    "res_country_state": ("id", "code"),
    "uom_uom": ("id", "name", "active"),
    "account_tax": ("id", "name", "amount", "type_tax_use", "active"),
    "account_tax_repartition_line": (
        "id", "tax_id", "repartition_type", "document_type", "factor_percent",
    ),
    "account_payment_term": ("id", "name", "active"),
    "product_category": ("id", "name", "parent_id"),
    "product_template": (
        "id", "categ_id", "uom_id", "type", "is_storable", "default_code",
        "name", "description_sale", "description", "list_price", "active",
    ),
    "product_product": ("id", "product_tmpl_id", "default_code", "barcode", "active"),
    "product_supplierinfo": (
        "id", "partner_id", "product_tmpl_id", "price", "discount", "min_qty",
        "delay", "sequence", "product_code", "product_name",
    ),
    "product_pricelist_item": ("id", "pricelist_id", "product_tmpl_id", "product_id"),
    "sale_order": (
        "id", "name", "state", "partner_id", "payment_term_id", "client_order_ref",
        "origin", "note", "validity_date", "date_order", "delivery_status",
        "invoice_status", "commitment_date", "amount_total", "amount_untaxed",
    ),
    "sale_order_line": (
        "id", "order_id", "sequence", "product_id", "product_uom_id", "display_type",
        "name", "product_uom_qty", "price_unit", "discount", "price_subtotal",
        "qty_delivered", "purchase_price",
    ),
    "account_tax_sale_order_line_rel": ("sale_order_line_id", "account_tax_id"),
    "purchase_order": (
        "id", "name", "state", "partner_id", "payment_term_id", "partner_ref",
        "origin", "note", "date_order", "date_planned", "receipt_status",
        "amount_total", "amount_untaxed",
    ),
    "purchase_order_line": (
        "id", "order_id", "sequence", "uom_id", "product_id", "display_type",
        "name", "product_qty", "price_unit", "discount", "price_subtotal", "qty_received",
    ),
    "account_tax_purchase_order_line_rel": ("purchase_order_line_id", "account_tax_id"),
    "account_move": (
        "id", "name", "move_type", "state", "payment_state", "partner_id",
        "invoice_payment_term_id", "ref", "invoice_origin", "invoice_date", "date",
        "invoice_date_due", "narration", "amount_total", "amount_untaxed",
    ),
    "account_move_line": (
        "id", "move_id", "sequence", "product_id", "product_uom_id", "display_type",
        "name", "quantity", "price_unit", "discount", "price_subtotal",
    ),
    "account_move_line_account_tax_rel": ("account_move_line_id", "account_tax_id"),
    "stock_quant": ("product_id", "location_id", "quantity"),
    "stock_location": ("id", "complete_name", "usage", "active"),
}

# Righe di questi tipi: descrizioni di testo che non entrano nei totali.
DISPLAY_MAP = {
    "line_section": LINE_SECTION,
    "line_subsection": LINE_SUBSECTION,
    "line_note": LINE_NOTE,
}

# Codici delle unità di misura di Odoo che corrispondono alle nostre.
UNIT_ALIAS = {
    "unità": "PZ", "unita": "PZ", "pezzi": "PZ", "pz": "PZ", "unit": "PZ",
    "ore": "H", "hours": "H", "hour": "H",
    "giorni": "GG", "days": "GG",
    "metri": "MT", "m": "MT",
    "m²": "MQ", "mq": "MQ", "m2": "MQ",
    "m³": "MC", "mc": "MC", "m3": "MC",
    "kg": "KG", "chilogrammi": "KG",
    "g": "GR", "grammi": "GR",
    "l": "LT", "lt": "LT", "litri": "LT", "liters": "LT",
    "km": "KM", "chilometri": "KM",
}


def _unescape(valore):
    """Scioglie i sequenze di fuga del formato COPY di PostgreSQL (\\t, \\n…)."""
    if "\\" not in valore:
        return valore
    fuori = []
    i = 0
    while i < len(valore):
        car = valore[i]
        if car == "\\" and i + 1 < len(valore):
            prossimo = valore[i + 1]
            fuori.append(
                {"t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}.get(
                    prossimo, prossimo
                )
            )
            i += 2
        else:
            fuori.append(car)
            i += 1
    return "".join(fuori)


def carica_dump(percorso):
    """Legge il dump (pg_dump formato plain) e rende le tabelle di interesse.

    Il file viene scorso una riga alla volta: i blocchi COPY delle tabelle che
    non servono vengono saltati senza decodificarli, così la memoria resta
    limitata anche con dump da centinaia di megabyte.
    """
    dati = {nome: [] for nome in TABELLE}
    corrente = None
    indici = None
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            riga = riga.rstrip("\n").rstrip("\r")
            if corrente is None:
                if riga.startswith("COPY public."):
                    resto = riga[len("COPY public."):]
                    nome, _, coda = resto.partition(" ")
                    if nome in TABELLE and "(" in coda:
                        colonne = [c.strip() for c in coda[coda.index("(") + 1:coda.index(")")].split(",")]
                        indici = [colonne.index(c) if c in colonne else None for c in TABELLE[nome]]
                        corrente = nome
                    else:
                        corrente = ""
                continue
            if riga == "\\.":
                corrente = None
                indici = None
                continue
            if corrente == "":
                continue
            valori = riga.split("\t")
            record = {}
            for nome_col, posizione in zip(TABELLE[corrente], indici):
                valore = valori[posizione] if posizione is not None and posizione < len(valori) else None
                record[nome_col] = None if valore in (None, "\\N") else _unescape(valore)
            dati[corrente].append(record)
    return dati


def _it(valore):
    """Nome tradotto: le tabelle recenti di Odoo salvano i nomi come JSON."""
    if valore and valore.startswith("{"):
        try:
            dizionario = json.loads(valore)
        except json.JSONDecodeError:
            return valore
        return dizionario.get("it_IT") or dizionario.get("en_US") or next(iter(dizionario.values()), "")
    return valore or ""


def _dec(valore, cifre="0.0001"):
    if valore in (None, ""):
        return Decimal("0")
    try:
        return Decimal(valore).quantize(Decimal(cifre), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0")


def _data(valore):
    if not valore:
        return None
    try:
        return datetime.strptime(valore[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _data_ora(valore):
    data = _data(valore)
    if data is None:
        return None
    return timezone.make_aware(datetime.combine(data, datetime.min.time().replace(hour=12)))


def _html_testo(valore):
    """Note di Odoo (TinyMCE): via i tag, restano i testi su righe separate."""
    if not valore:
        return ""
    testo = re.sub(r"<\s*(br|/p|/div|/li|/tr)[^>]*>", "\n", valore, flags=re.I)
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = html.unescape(testo)
    righe = [r.strip() for r in testo.splitlines()]
    return "\n".join(r for r in righe if r).strip()


def _comprimi(valore):
    return " ".join((valore or "").split())


def _int(valore):
    try:
        return int(float(valore or 0))
    except (TypeError, ValueError):
        return 0


class Importatore:
    """Trasforma i dati letti dal dump in record del gestionale."""

    def __init__(self, dati, stdout, style=None):
        self.dati = dati
        self.stdout = stdout
        self.style = style or color_style()
        self.avvisi = []
        self.conteggi = {}
        self.mappa_contatti = {}
        self.mappa_prodotti = {}
        self.mappa_unita = {}
        self.mappa_iva = {}
        self.mappa_pagamenti = {}
        self.mappa_categorie = {}
        self.differenze = []

    # ------------------------------------------------------------ utilità
    def _avviso(self, messaggio):
        self.avvisi.append(messaggio)

    # ---------------------------------------------------------- anteprima
    def prepara(self):
        """Calcola gli insiemi di riferimento senza toccare il database."""
        self.variante_template = {
            v["id"]: v["product_tmpl_id"] for v in self.dati["product_product"]
        }
        self.loc_interne = {
            loc["id"] for loc in self.dati["stock_location"] if loc["usage"] == "internal"
        }
        clienti = {o["partner_id"] for o in self.dati["sale_order"] if o["partner_id"]}
        clienti |= {m["partner_id"] for m in self.dati["account_move"] if m["partner_id"]}
        fornitori = {o["partner_id"] for o in self.dati["purchase_order"] if o["partner_id"]}
        fornitori |= {
            r["partner_id"] for r in self.dati["product_supplierinfo"] if r["partner_id"]
        }
        self.partner_clienti = clienti
        self.partner_fornitori = fornitori
        riferiti = clienti | fornitori

        tenuti = set()
        for r in self.dati["product_supplierinfo"]:
            if r["product_tmpl_id"]:
                tenuti.add(r["product_tmpl_id"])
        for r in self.dati["product_pricelist_item"]:
            if r["product_tmpl_id"]:
                tenuti.add(r["product_tmpl_id"])
            if r["product_id"]:
                tenuti.add(self.variante_template.get(r["product_id"]))
        for tabella, campo in (
            ("sale_order_line", "product_id"),
            ("purchase_order_line", "product_id"),
            ("account_move_line", "product_id"),
        ):
            for r in self.dati[tabella]:
                if r[campo]:
                    tenuti.add(self.variante_template.get(r[campo]))
        for q in self.dati["stock_quant"]:
            if q["location_id"] in self.loc_interne and _dec(q["quantity"], "0.001") != 0:
                if q["product_id"]:
                    tenuti.add(self.variante_template.get(q["product_id"]))
        tenuti.discard(None)
        self.template_tenuti = tenuti
        return self

    def partner_da_importare(self):
        tenuti = []
        for r in self.dati["res_partner"]:
            attivo = r["active"] == "t"
            cliente = _int(r["customer_rank"]) > 0
            fornitore = _int(r["supplier_rank"]) > 0
            riferito = r["id"] in self.partner_clienti or r["id"] in self.partner_fornitori
            if (attivo and (cliente or fornitore)) or riferito:
                tenuti.append(r)
        return tenuti

    def anteprima(self):
        self.prepara()
        vendite = self.dati["sale_order"]
        quote = sum(1 for o in vendite if o["state"] in ("draft", "sent", "cancel"))
        ordini = sum(1 for o in vendite if o["state"] not in ("draft", "sent", "cancel"))
        fatture = [m for m in self.dati["account_move"] if m["move_type"] == "out_invoice"]
        giacenze = sum(
            1
            for q in self.dati["stock_quant"]
            if q["location_id"] in self.loc_interne
            and _dec(q["quantity"], "0.001") != 0
            and q["product_id"] in self.variante_template
        )
        righe = len(self.dati["sale_order_line"]) + len(self.dati["purchase_order_line"])
        self.stdout.write("Anteprima importazione Odoo:")
        self.stdout.write(f"  contatti da importare:        {len(self.partner_da_importare())}")
        self.stdout.write(f"  categorie:                    {len(self.dati['product_category'])}")
        self.stdout.write(f"  articoli (template tenuti):   {len(self.template_tenuti)}")
        self.stdout.write(f"  voci di listino fornitore:    {len(self.dati['product_supplierinfo'])}")
        self.stdout.write(f"  preventivi:                   {quote}")
        self.stdout.write(f"  ordini cliente:               {ordini}")
        self.stdout.write(f"  ordini fornitore:             {len(self.dati['purchase_order'])}")
        self.stdout.write(f"  fatture emesse:               {len(fatture)}")
        self.stdout.write(f"  righe di documento:           {righe}")
        self.stdout.write(f"  giacenze da importare:        {giacenze}")

    # ------------------------------------------------------- svuotamento
    def svuota(self):
        """Cancella i dati di dominio; restano utenti, ruoli e configurazioni."""
        sequenza = [
            ("core", "EmailInCoda"), ("core", "ActivityLog"), ("core", "InternalMessage"),
            ("core", "InboundEmail"), ("core", "Attachment"), ("core", "WikiPage"),
            ("gallery", "GalleryPhoto"), ("gallery", "GalleryTag"),
            ("leads", "Lead"),
            ("jobs", "MaintenancePlan"), ("jobs", "Job"),
            ("hr", "CollaboratorTimeEntry"), ("hr", "Collaborator"), ("hr", "TimeEntry"),
            ("hr", "LeaveRequest"), ("hr", "Employee"),
            ("billing", "SalesInvoiceLine"), ("billing", "SalesInvoice"),
            ("billing", "PurchaseInvoiceLine"), ("billing", "PurchaseInvoice"),
            ("billing", "DeliveryNoteLine"), ("billing", "DeliveryNote"),
            ("sales", "SalesOrderLine"), ("sales", "SalesOrder"),
            ("sales", "QuoteLine"), ("sales", "Quote"),
            ("sales", "QuoteTemplateLine"), ("sales", "QuoteTemplate"),
            ("purchasing", "PurchaseOrderLine"), ("purchasing", "PurchaseOrder"),
            ("purchasing", "PriceListItem"), ("purchasing", "PriceListAdjustment"),
            ("purchasing", "SupplierPriceList"),
            ("inventory", "StockMovement"), ("inventory", "StockLevel"),
            ("catalog", "KitComponent"), ("catalog", "Product"), ("catalog", "Category"),
            ("contacts", "Contact"), ("core", "Tag"),
        ]
        totale = 0
        for etichetta, modello in sequenza:
            quante, _ = django_apps.get_model(etichetta, modello).objects.all().delete()
            totale += quante
        self.conteggi["righe eliminate"] = totale

    # --------------------------------------------------------- mappature
    def importa_unita(self):
        """Unità di misura usate dai template tenuti e dalle righe dei documenti."""
        usate = set()
        for t in self.dati["product_template"]:
            if t["id"] in self.template_tenuti and t["uom_id"]:
                usate.add(t["uom_id"])
        for r in self.dati["sale_order_line"]:
            if r["product_uom_id"]:
                usate.add(r["product_uom_id"])
        for r in self.dati["purchase_order_line"]:
            if r["uom_id"]:
                usate.add(r["uom_id"])
        for r in self.dati["account_move_line"]:
            if r["product_uom_id"]:
                usate.add(r["product_uom_id"])
        per_id = {u["id"]: u for u in self.dati["uom_uom"]}
        for uom_id in sorted(usate):
            riga = per_id.get(uom_id)
            nome = _it(riga["name"]) if riga else ""
            chiave = nome.strip().lower()
            codice = UNIT_ALIAS.get(chiave)
            unita = None
            if codice:
                unita = UnitOfMeasure.objects.filter(code=codice).first()
            if unita is None and nome:
                unita = UnitOfMeasure.objects.filter(name__iexact=nome).first()
            if unita is None:
                codice = re.sub(r"[^A-Za-z0-9]", "", nome.upper())[:10] or f"U{uom_id}"
                unita = UnitOfMeasure.objects.filter(code=codice).first()
                if unita is None:
                    unita = UnitOfMeasure.objects.create(code=codice, name=(nome or codice)[:60])
                    self.conteggi.setdefault("unità create", 0)
                    self.conteggi["unità create"] += 1
            self.mappa_unita[uom_id] = unita
        self.unita_predefinita = (
            UnitOfMeasure.objects.filter(code="PZ").first()
            or UnitOfMeasure.objects.order_by("pk").first()
        )

    def _unita(self, uom_id):
        return self.mappa_unita.get(uom_id) or self.unita_predefinita

    def importa_iva(self):
        """Aliquote delle righe, calcolate dall'effetto reale nei totali.

        Le imposte di Odoo non si leggono dalla sola aliquota: il reverse
        charge (es. «22% M IC») ha aliquota 22% ma le sue righe di repartition
        si annullano, quindi non aggiunge IVA ai totali. L'effetto effettivo si
        ricava sommando i fattori delle repartition delle fatture.
        """
        self.tasse = {t["id"]: t for t in self.dati["account_tax"]}
        fattori = defaultdict(float)
        for r in self.dati["account_tax_repartition_line"]:
            if r["repartition_type"] == "tax" and r["document_type"] == "invoice":
                try:
                    fattori[r["tax_id"]] += float(r["factor_percent"] or 0)
                except ValueError:
                    pass
        self.iva_vendita = (
            VatRate.default_for_sales() or VatRate.objects.order_by("-rate").first()
        )
        self.iva_acquisto = (
            VatRate.default_for_purchase() or VatRate.objects.order_by("-rate").first()
        )
        self.iva_zero = VatRate.objects.filter(code="0").first() or self.iva_vendita
        mappa_codici = {"22.00": "22", "10.00": "10", "5.00": "5", "4.00": "4", "0.00": "0"}
        usate = set()
        for tabella, campo in (
            ("account_tax_sale_order_line_rel", "account_tax_id"),
            ("account_tax_purchase_order_line_rel", "account_tax_id"),
            ("account_move_line_account_tax_rel", "account_tax_id"),
        ):
            for r in self.dati[tabella]:
                if r[campo]:
                    usate.add(r[campo])
        for tassa_id in sorted(usate):
            tassa = self.tasse.get(tassa_id)
            if tassa is None:
                self.mappa_iva[tassa_id] = None
                continue
            importo = _dec(tassa["amount"])
            fattore = fattori.get(tassa_id, 100.0)
            effettiva = (importo * Decimal(str(fattore)) / 100).quantize(Decimal("0.01"))
            if effettiva == 0 and importo != 0:
                codice = "N6"  # reverse charge: aliquota senza effetto sui totali
            else:
                codice = mappa_codici.get(f"{effettiva:.2f}")
            voce = VatRate.objects.filter(code=codice).first() if codice else None
            if voce is None and codice is None:
                self._avviso(
                    f"aliquota Odoo «{_it(tassa['name'])}» ({importo}%): uso l'aliquota predefinita"
                )
            self.mappa_iva[tassa_id] = voce  # None = si userà la predefinita

    def _aliquota(self, tassa_id, acquisto=False):
        if not tassa_id:
            # riga senza imposta in Odoo: niente IVA, non l'aliquota predefinita
            return self.iva_zero
        voce = self.mappa_iva.get(tassa_id)
        if voce is not None:
            return voce
        return self.iva_acquisto if acquisto else self.iva_vendita

    def _pagamento(self, termine_id):
        if not termine_id:
            return None
        if termine_id in self.mappa_pagamenti:
            return self.mappa_pagamenti[termine_id]
        righe = {t["id"]: t for t in self.dati["account_payment_term"]}
        nome = _comprimi(_it(righe[termine_id]["name"])) if termine_id in righe else ""
        if not nome:
            nome = f"Condizione {termine_id}"
        cerca = re.search(r"(\d+)\s*giorni", nome)
        if cerca:
            giorni = int(cerca.group(1))
        else:
            numeri = re.findall(r"(\d+)", nome.split(",")[-1] if "," in nome else nome)
            giorni = int(numeri[-1]) if numeri else 0
        fine_mese = "fine mese" in nome.lower()
        termine, creato = PaymentTerm.objects.get_or_create(
            name=nome[:80], defaults={"days": giorni, "end_of_month": fine_mese}
        )
        if creato:
            self.conteggi.setdefault("condizioni create", 0)
            self.conteggi["condizioni create"] += 1
        self.mappa_pagamenti[termine_id] = termine
        return termine

    def importa_categorie(self):
        for r in sorted(self.dati["product_category"], key=lambda x: int(x["id"])):
            nome = _comprimi(_it(r["name"]))[:100] or f"Categoria {r['id']}"
            categoria, _ = Category.objects.get_or_create(name=nome)
            self.mappa_categorie[r["id"]] = categoria
        for r in self.dati["product_category"]:
            if r["parent_id"] and r["parent_id"] in self.mappa_categorie:
                categoria = self.mappa_categorie[r["id"]]
                genitore = self.mappa_categorie[r["parent_id"]]
                if categoria.parent_id != genitore.pk:
                    categoria.parent = genitore
                    categoria.save(update_fields=["parent"])
        self.conteggi["categorie"] = Category.objects.count()

    # ------------------------------------------------------------ contatti
    def importa_contatti(self):
        stati = {r["id"]: r["code"] for r in self.dati["res_country_state"]}
        paesi = {r["id"]: _comprimi(_it(r["name"])) for r in self.dati["res_country"]}
        importati = 0
        for r in sorted(self.partner_da_importare(), key=lambda x: int(x["id"])):
            cliente = _int(r["customer_rank"]) > 0 or r["id"] in self.partner_clienti
            fornitore = _int(r["supplier_rank"]) > 0 or r["id"] in self.partner_fornitori
            piva = (r["vat"] or "").strip().upper()
            if re.match(r"^IT\d{11}$", piva):
                piva = piva[2:]
            email = ""
            for _, indirizzo in getaddresses([r["email"] or ""]):
                if "@" in indirizzo:
                    email = indirizzo
                    break
            indirizzo = _comprimi(f"{r['street'] or ''} {r['street2'] or ''}")
            paese = paesi.get(r["country_id"], "")
            termine = self._pagamento(
                r["property_payment_term_id"] if cliente else r["property_supplier_payment_term_id"]
            ) or self._pagamento(
                r["property_supplier_payment_term_id"]
                if cliente
                else r["property_payment_term_id"]
            )
            contatto = Contact(
                name=_comprimi(r["name"])[:200] or f"Contatto {r['id']}",
                is_customer=cliente,
                is_supplier=fornitore,
                vat_number=piva[:20],
                tax_code=_comprimi(r["l10n_it_codice_fiscale"]).upper()[:20],
                sdi_code=_comprimi(r["l10n_it_pa_index"]).upper()[:10],
                pec=(r["l10n_it_pec_email"] or "").strip()[:254],
                email=email[:254],
                phone=_comprimi(r["phone"])[:40],
                website=(r["website"] or "").strip()[:200],
                address=indirizzo[:200],
                zip_code=_comprimi(r["zip"])[:10],
                city=_comprimi(r["city"])[:100],
                province=(stati.get(r["state_id"]) or "")[:5].upper(),
                country=paese[:100] or "Italia",
                payment_term=termine,
                notes=_html_testo(r["comment"]),
                active=r["active"] == "t",
            )
            contatto.save()
            self.mappa_contatti[r["id"]] = contatto
            importati += 1
        self.conteggi["contatti"] = importati

    # ------------------------------------------------------------ articoli
    def _codice_libero(self, codice, usati):
        base = codice[:36]
        contatore = 2
        nuovo = f"{base}-{contatore}"
        while nuovo in usati:
            contatore += 1
            nuovo = f"{base}-{contatore}"
        return nuovo[:40]

    def importa_prodotti(self):
        varianti = defaultdict(list)
        for v in self.dati["product_product"]:
            varianti[v["product_tmpl_id"]].append(v)
        forniture = defaultdict(list)
        for r in self.dati["product_supplierinfo"]:
            forniture[r["product_tmpl_id"]].append(r)
        codici_usati = set(Product.objects.values_list("code", flat=True))
        righe = []
        ordine_template = []
        for t in sorted(self.dati["product_template"], key=lambda x: int(x["id"])):
            if t["id"] not in self.template_tenuti:
                continue
            nome = _comprimi(_it(t["name"]))[:200] or f"Articolo {t['id']}"
            varianti_t = varianti.get(t["id"], [])
            codice = _comprimi(t["default_code"])
            if not codice:
                codice = next(
                    (_comprimi(v["default_code"]) for v in varianti_t if _comprimi(v["default_code"])),
                    "",
                )
            codice = codice[:40]
            if codice and codice in codici_usati:
                codice = self._codice_libero(codice, codici_usati)
            elif not codice:
                codice = f"TMP-{t['id']}"
                while codice in codici_usati:
                    codice += "x"
            codici_usati.add(codice)
            barcode = next((v["barcode"] for v in varianti_t if v["barcode"]), "")
            disponibili = sorted(
                forniture.get(t["id"], []), key=lambda x: (int(x["sequence"] or 0), int(x["id"]))
            )
            fornitore = (
                self.mappa_contatti.get(disponibili[0]["partner_id"]) if disponibili else None
            )
            righe.append(
                Product(
                    code=codice,
                    name=nome,
                    description=_it(t["description_sale"]) or _it(t["description"]) or "",
                    category=self.mappa_categorie.get(t["categ_id"]),
                    uom=self._unita(t["uom_id"]),
                    barcode=barcode[:50],
                    sale_price=_dec(t["list_price"]),
                    sale_vat=self.iva_vendita,
                    purchase_price=Decimal("0"),
                    purchase_vat=self.iva_acquisto,
                    main_supplier=fornitore,
                    supplier_lead_days=int(disponibili[0]["delay"] or 0) if disponibili else 0,
                    is_stock_tracked=(t["type"] == "consu" and t["is_storable"] == "t"),
                    active=t["active"] == "t",
                )
            )
            ordine_template.append(t["id"])
        creati = Product.objects.bulk_create(righe, batch_size=400)
        senza_codice = [p for p in creati if p.code.startswith("TMP")]
        for prodotto in senza_codice:
            candidato = f"ART{prodotto.pk:05d}"
            if candidato in codici_usati:
                candidato = self._codice_libero(candidato, codici_usati)
            codici_usati.add(candidato)
            prodotto.code = candidato
        if senza_codice:
            Product.objects.bulk_update(senza_codice, ["code"], batch_size=400)
        for tmpl_id, prodotto in zip(ordine_template, creati):
            self.mappa_prodotti[tmpl_id] = prodotto
            for v in varianti.get(tmpl_id, []):
                self.mappa_prodotti[v["id"]] = prodotto
        self.conteggi["articoli"] = len(creati)
        if senza_codice:
            self.conteggi["articoli senza codice (rinumerati)"] = len(senza_codice)

    # ------------------------------------------------------------ listini
    def importa_listini(self):
        per_fornitore = defaultdict(list)
        for r in self.dati["product_supplierinfo"]:
            if r["product_tmpl_id"] in self.template_tenuti and r["partner_id"] in self.mappa_contatti:
                per_fornitore[r["partner_id"]].append(r)
        voci_totali = 0
        for partner_id, righe in sorted(per_fornitore.items()):
            listino = SupplierPriceList.objects.create(
                supplier=self.mappa_contatti[partner_id],
                name="Listino principale",
                notes="Importato da Odoo",
            )
            scelti = {}
            for r in sorted(righe, key=lambda x: (int(x["sequence"] or 0), int(x["id"]))):
                scelti.setdefault(r["product_tmpl_id"], r)
            voci = []
            for tmpl_id, r in scelti.items():
                prodotto = self.mappa_prodotti.get(tmpl_id)
                if prodotto is None:
                    continue
                voci.append(
                    PriceListItem(
                        pricelist=listino,
                        product=prodotto,
                        supplier_code=_comprimi(r["product_code"])[:60],
                        price=_dec(r["price"]),
                        discount_pct=_dec(r["discount"], "0.01"),
                        min_qty=_dec(r["min_qty"], "0.001"),
                        note=_comprimi(_it(r["product_name"]))[:200],
                    )
                )
            PriceListItem.objects.bulk_create(voci, batch_size=400)
            voci_totali += len(voci)
        self.conteggi["listini fornitori"] = SupplierPriceList.objects.count()
        self.conteggi["voci di listino"] = voci_totali

    # ------------------------------------------------- documenti di vendita
    def _riga(self, modello, r, campo_uom, campo_qta, tasse, acquisto):
        tipo = DISPLAY_MAP.get(r["display_type"], LINE_ARTICLE)
        prodotto = self.mappa_prodotti.get(r["product_id"]) if r["product_id"] else None
        if tipo == LINE_ARTICLE:
            descrizione = _comprimi(r["name"])
            if prodotto is not None:
                match = re.match(r"^\[([^\]]+)\]\s*", descrizione)
                if match:
                    codice = (prodotto.code or "").rstrip(".").lower()
                    dentro = match.group(1).strip().rstrip(".").lower()
                    if codice and (dentro == codice or dentro in codice or codice in dentro):
                        descrizione = descrizione[match.end():]
        else:
            descrizione = _comprimi(_html_testo(r["name"]) or r["name"])
        campi = {
            "position": int(r["sequence"] or 0),
            "line_type": tipo,
            "product": prodotto if tipo == LINE_ARTICLE else None,
            "description": descrizione[:300],
            "qty": _dec(r[campo_qta], "0.001") if tipo == LINE_ARTICLE else Decimal("0"),
            "uom": self._unita(r[campo_uom]) if tipo == LINE_ARTICLE else None,
            "unit_price": _dec(r["price_unit"]) if tipo == LINE_ARTICLE else Decimal("0"),
            "discount_pct": _dec(r["discount"], "0.01") if tipo == LINE_ARTICLE else Decimal("0"),
            "vat_rate": self._aliquota((tasse.get(r["id"]) or [None])[0], acquisto=acquisto)
            if tipo == LINE_ARTICLE
            else None,
        }
        riga = modello(**campi)
        return riga

    def importa_vendite(self):
        righe_per_ordine = defaultdict(list)
        for r in self.dati["sale_order_line"]:
            righe_per_ordine[r["order_id"]].append(r)
        tasse = defaultdict(list)
        for r in self.dati["account_tax_sale_order_line_rel"]:
            tasse[r["sale_order_line_id"]].append(r["account_tax_id"])
        totali = defaultdict(lambda: [Decimal("0"), Decimal("0")])
        documenti = []  # (modello, documento, id Odoo, totale atteso da Odoo)
        ordinati = sorted(
            self.dati["sale_order"], key=lambda x: (x["date_order"] or "", int(x["id"]))
        )
        # 1) Preventivi (compresi gli annullati, che restano come «rifiutato»).
        quote_odoo = {}
        for o in ordinati:
            if o["state"] not in ("draft", "sent", "cancel"):
                continue
            cliente = self.mappa_contatti.get(o["partner_id"])
            if cliente is None:
                self._avviso(f"preventivo {o['name']}: cliente non importato, saltato")
                continue
            documento = Quote.objects.create(
                number=_comprimi(o["name"])[:30],
                date=_data(o["date_order"]),
                customer=cliente,
                payment_term=self._pagamento(o["payment_term_id"]),
                reference=_comprimi(o["client_order_ref"])[:100],
                notes=_html_testo(o["note"]),
                valid_until=_data(o["validity_date"]),
                status={
                    "draft": Quote.STATUS_DRAFT,
                    "sent": Quote.STATUS_SENT,
                    "cancel": Quote.STATUS_REJECTED,
                }[o["state"]],
            )
            quote_odoo[o["id"]] = documento
            documenti.append((Quote, documento, o["id"], _dec(o["amount_total"], "0.01")))
        # 2) Ordini cliente, collegati al preventivo di partenza quando c'è.
        quote_per_numero = {q.number: q for q in Quote.objects.exclude(number="")}
        ordini_odoo = {}
        for o in ordinati:
            if o["state"] in ("draft", "sent", "cancel"):
                continue
            cliente = self.mappa_contatti.get(o["partner_id"])
            if cliente is None:
                self._avviso(f"ordine {o['name']}: cliente non importato, saltato")
                continue
            consegnato = o["delivery_status"] == "full"
            quando = _data_ora(o["date_order"])
            documento = SalesOrder.objects.create(
                number=_comprimi(o["name"])[:30],
                date=_data(o["date_order"]),
                customer=cliente,
                payment_term=self._pagamento(o["payment_term_id"]),
                reference=_comprimi(o["client_order_ref"])[:100],
                notes=_html_testo(o["note"]),
                expected_date=_data(o["commitment_date"]),
                source_quote=quote_per_numero.get(_comprimi(o["origin"])[:30]),
                status=SalesOrder.STATUS_DELIVERED if consegnato else SalesOrder.STATUS_CONFIRMED,
                confirmed_at=quando,
                delivered_at=quando if consegnato else None,
            )
            ordini_odoo[o["id"]] = documento
            documenti.append((SalesOrder, documento, o["id"], _dec(o["amount_total"], "0.01")))
        # 3) I preventivi che hanno generato un ordine risultano «convertiti».
        origini = {
            _comprimi(o["origin"])[:30]
            for o in ordinati
            if o["state"] not in ("draft", "sent", "cancel") and _comprimi(o["origin"])
        }
        convertiti = [q.pk for q in quote_odoo.values() if q.number in origini]
        if convertiti:
            Quote.objects.filter(pk__in=convertiti).update(status=Quote.STATUS_CONVERTED)
        # 4) Righe di tutti i documenti.
        righe_quote, righe_ordini = [], []
        for o in ordinati:
            documento = quote_odoo.get(o["id"]) or ordini_odoo.get(o["id"])
            if documento is None:
                continue
            quote_doc = isinstance(documento, Quote)
            for r in sorted(righe_per_ordine.get(o["id"], []), key=lambda x: (int(x["sequence"] or 0), int(x["id"]))):
                if quote_doc:
                    riga = self._riga(QuoteLine, r, "product_uom_id", "product_uom_qty", tasse, acquisto=False)
                    riga.quote = documento
                    righe_quote.append(riga)
                else:
                    riga = self._riga(SalesOrderLine, r, "product_uom_id", "product_uom_qty", tasse, acquisto=False)
                    riga.order = documento
                    riga.qty_delivered = (
                        _dec(r["qty_delivered"], "0.001") if r["display_type"] not in DISPLAY_MAP.values() else Decimal("0")
                    )
                    costo = _dec(r["purchase_price"])
                    if costo:
                        riga.unit_cost = costo
                    righe_ordini.append(riga)
                totali[o["id"]][0] += riga.line_subtotal
                totali[o["id"]][1] += riga.line_vat
        QuoteLine.objects.bulk_create(righe_quote, batch_size=400)
        SalesOrderLine.objects.bulk_create(righe_ordini, batch_size=400)
        for modello in (Quote, SalesOrder):
            aggiornati = []
            for modello_doc, doc, odoo_id, atteso in documenti:
                if modello_doc is not modello:
                    continue
                subtotale, iva = totali[odoo_id]
                doc.subtotal = round2(subtotale)
                doc.vat_total = round2(iva)
                doc.grand_total = round2(doc.subtotal + doc.vat_total)
                aggiornati.append(doc)
                if abs(doc.grand_total - atteso) > Decimal("0.05"):
                    self.differenze.append((doc.number, doc.grand_total, atteso))
            modello.objects.bulk_update(aggiornati, ["subtotal", "vat_total", "grand_total"], batch_size=400)
        self.conteggi["preventivi"] = Quote.objects.count()
        self.conteggi["ordini cliente"] = SalesOrder.objects.count()
        self.conteggi["righe preventivo/ordine"] = len(righe_quote) + len(righe_ordini)

    # ---------------------------------------------------- documenti acquisto
    def importa_acquisti(self):
        righe_per_ordine = defaultdict(list)
        for r in self.dati["purchase_order_line"]:
            righe_per_ordine[r["order_id"]].append(r)
        tasse = defaultdict(list)
        for r in self.dati["account_tax_purchase_order_line_rel"]:
            tasse[r["purchase_order_line_id"]].append(r["account_tax_id"])
        totali = defaultdict(lambda: [Decimal("0"), Decimal("0")])
        ordini_odoo = {}
        attesi = {}
        for o in sorted(self.dati["purchase_order"], key=lambda x: (x["date_order"] or "", int(x["id"]))):
            fornitore = self.mappa_contatti.get(o["partner_id"])
            if fornitore is None:
                self._avviso(f"ordine fornitore {o['name']}: fornitore non importato, saltato")
                continue
            if o["state"] == "draft":
                stato = PurchaseOrder.STATUS_DRAFT
            elif o["state"] == "cancel":
                stato = PurchaseOrder.STATUS_CANCELLED
            elif o["receipt_status"] == "full":
                stato = PurchaseOrder.STATUS_RECEIVED
            elif o["receipt_status"] == "partial":
                stato = PurchaseOrder.STATUS_PARTIAL
            else:
                stato = PurchaseOrder.STATUS_CONFIRMED
            note = []
            if _comprimi(o["partner_ref"]):
                note.append(f"Rif. fornitore: {_comprimi(o['partner_ref'])}")
            if _comprimi(o["origin"]):
                note.append(f"Origine: {_comprimi(o['origin'])}")
            testo_note = _html_testo(o["note"])
            if testo_note:
                note.append(testo_note)
            documento = PurchaseOrder.objects.create(
                number=_comprimi(o["name"])[:30],
                date=_data(o["date_order"]),
                expected_date=_data(o["date_planned"]),
                supplier=fornitore,
                payment_term=self._pagamento(o["payment_term_id"]),
                notes="\n".join(note),
                status=stato,
            )
            ordini_odoo[o["id"]] = documento
            attesi[documento.pk] = _dec(o["amount_total"], "0.01")
        righe = []
        for o in self.dati["purchase_order"]:
            documento = ordini_odoo.get(o["id"])
            if documento is None:
                continue
            for r in sorted(righe_per_ordine.get(o["id"], []), key=lambda x: (int(x["sequence"] or 0), int(x["id"]))):
                riga = self._riga(PurchaseOrderLine, r, "uom_id", "product_qty", tasse, acquisto=True)
                riga.po = documento
                riga.qty_received = (
                    _dec(r["qty_received"], "0.001") if r["display_type"] not in DISPLAY_MAP.values() else Decimal("0")
                )
                righe.append(riga)
                totali[documento.pk][0] += riga.line_subtotal
                totali[documento.pk][1] += riga.line_vat
        PurchaseOrderLine.objects.bulk_create(righe, batch_size=400)
        aggiornati = []
        for doc in PurchaseOrder.objects.all():
            subtotale, iva = totali[doc.pk]
            doc.subtotal = round2(subtotale)
            doc.vat_total = round2(iva)
            doc.grand_total = round2(doc.subtotal + doc.vat_total)
            aggiornati.append(doc)
            atteso = attesi.get(doc.pk)
            if atteso is not None and abs(doc.grand_total - atteso) > Decimal("0.05"):
                self.differenze.append((doc.number, doc.grand_total, atteso))
        PurchaseOrder.objects.bulk_update(aggiornati, ["subtotal", "vat_total", "grand_total"], batch_size=400)
        self.conteggi["ordini fornitore"] = PurchaseOrder.objects.count()
        self.conteggi["righe ordine fornitore"] = len(righe)

    # ------------------------------------------------------------ fatture
    def importa_fatture(self):
        from apps.billing.models import SalesInvoice, SalesInvoiceLine

        righe_per_move = defaultdict(list)
        for r in self.dati["account_move_line"]:
            righe_per_move[r["move_id"]].append(r)
        tasse = defaultdict(list)
        for r in self.dati["account_move_line_account_tax_rel"]:
            tasse[r["account_move_line_id"]].append(r["account_tax_id"])
        ordini_per_numero = {
            o.number: o for o in SalesOrder.objects.exclude(number="")
        }
        totali = defaultdict(lambda: [Decimal("0"), Decimal("0")])
        fatture_odoo = {}
        attesi = {}
        for m in sorted(self.dati["account_move"], key=lambda x: (x["invoice_date"] or x["date"] or "", int(x["id"]))):
            if m["move_type"] != "out_invoice":
                continue
            cliente = self.mappa_contatti.get(m["partner_id"])
            if cliente is None:
                self._avviso(f"fattura {m['name'] or m['id']}: cliente non importato, saltata")
                continue
            if m["state"] == "draft":
                stato = SalesInvoice.STATUS_DRAFT
            elif m["state"] == "cancel":
                stato = SalesInvoice.STATUS_CANCELLED
            elif m["payment_state"] == "paid":
                stato = SalesInvoice.STATUS_PAID
            else:
                stato = SalesInvoice.STATUS_ISSUED
            quando = _data_ora(m["invoice_date"] or m["date"])
            fattura = SalesInvoice(
                number=_comprimi(m["name"])[:30],
                date=_data(m["invoice_date"] or m["date"]),
                due_date=_data(m["invoice_date_due"]),
                customer=cliente,
                payment_term=self._pagamento(m["invoice_payment_term_id"]),
                reference=_comprimi(m["ref"])[:100],
                notes=_html_testo(m["narration"]),
                status=stato,
                issued_at=quando if stato != SalesInvoice.STATUS_DRAFT else None,
                paid_at=quando if stato == SalesInvoice.STATUS_PAID else None,
                source_order=ordini_per_numero.get(_comprimi(m["invoice_origin"])[:30]),
            )
            fattura.save()
            fatture_odoo[m["id"]] = fattura
            attesi[fattura.pk] = _dec(m["amount_total"], "0.01")
        righe = []
        for m in self.dati["account_move"]:
            fattura = fatture_odoo.get(m["id"])
            if fattura is None:
                continue
            for r in sorted(righe_per_move.get(m["id"], []), key=lambda x: int(x["id"])):
                if r["display_type"] not in (None, "product") and r["display_type"] not in DISPLAY_MAP:
                    continue  # scadenze, riepiloghi IVA: non sono righe di documento
                riga = self._riga(SalesInvoiceLine, r, "product_uom_id", "quantity", tasse, acquisto=False)
                riga.invoice = fattura
                righe.append(riga)
                totali[fattura.pk][0] += riga.line_subtotal
                totali[fattura.pk][1] += riga.line_vat
        SalesInvoiceLine.objects.bulk_create(righe, batch_size=400)
        aggiornate = []
        for fattura in SalesInvoice.objects.all():
            subtotale, iva = totali[fattura.pk]
            fattura.subtotal = round2(subtotale)
            fattura.vat_total = round2(iva)
            fattura.grand_total = round2(fattura.subtotal + fattura.vat_total)
            aggiornate.append(fattura)
            atteso = attesi.get(fattura.pk)
            if atteso is not None and abs(fattura.grand_total - atteso) > Decimal("0.05"):
                self.differenze.append((fattura.number, fattura.grand_total, atteso))
        SalesInvoice.objects.bulk_update(aggiornate, ["subtotal", "vat_total", "grand_total"], batch_size=400)
        self.conteggi["fatture emesse"] = SalesInvoice.objects.count()
        self.conteggi["righe fattura"] = len(righe)

    # ------------------------------------------------------------ giacenze
    def importa_giacenze(self):
        magazzino = Warehouse.get_default()
        if magazzino is None:
            magazzino = Warehouse.objects.create(
                code="MAG", name="Magazzino principale", is_default=True
            )
        aggregato = defaultdict(Decimal)
        for q in self.dati["stock_quant"]:
            if q["location_id"] not in self.loc_interne:
                continue
            prodotto = self.mappa_prodotti.get(q["product_id"])
            if prodotto is None:
                continue
            quantita = _dec(q["quantity"], "0.001")
            if quantita != 0:
                aggregato[prodotto] += quantita
        StockLevel.objects.bulk_create(
            [
                StockLevel(product=prodotto, warehouse=magazzino, quantity=quantita)
                for prodotto, quantita in aggregato.items()
            ],
            batch_size=400,
        )
        self.conteggi["giacenze"] = len(aggregato)

    # -------------------------------------------------------- numerazioni
    def prepara_numerazioni(self):
        for tipo in (
            NumberSequence.DOC_TYPE_QUOTE,
            NumberSequence.DOC_TYPE_SALES_ORDER,
            NumberSequence.DOC_TYPE_PURCHASE_ORDER,
            NumberSequence.DOC_TYPE_DELIVERY_NOTE,
            NumberSequence.DOC_TYPE_SALES_INVOICE,
            NumberSequence.DOC_TYPE_PURCHASE_INVOICE,
        ):
            NumberSequence.get_for(tipo)

    # ------------------------------------------------------------ sequenza
    def esegui(self):
        self.stdout.write("Svuotamento dei dati di prova…")
        self.svuota()
        self.prepara()
        self.importa_unita()
        self.importa_iva()
        self.stdout.write("Importazione contatti…")
        self.importa_categorie()
        self.importa_contatti()
        self.stdout.write("Importazione articoli e listini…")
        self.importa_prodotti()
        self.importa_listini()
        self.stdout.write("Importazione preventivi e ordini cliente…")
        self.importa_vendite()
        self.stdout.write("Importazione ordini fornitore…")
        self.importa_acquisti()
        self.stdout.write("Importazione fatture emesse…")
        self.importa_fatture()
        self.stdout.write("Importazione giacenze…")
        self.importa_giacenze()
        self.prepara_numerazioni()

    def riepilogo(self):
        self.stdout.write(self.style.SUCCESS("Importazione completata."))
        for etichetta, valore in self.conteggi.items():
            self.stdout.write(f"  {etichetta}: {valore}")
        if self.differenze:
            self.stdout.write(
                self.style.WARNING(
                    f"Totale diverso da Odoo su {len(self.differenze)} documenti (differenza > 5 centesimi):"
                )
            )
            for numero, nostro, atteso in self.differenze[:15]:
                self.stdout.write(f"  {numero}: nostro {nostro} €, Odoo {atteso} €")
            if len(self.differenze) > 15:
                self.stdout.write(f"  … e altri {len(self.differenze) - 15}")
        for messaggio in self.avvisi[:30]:
            self.stdout.write(self.style.WARNING(f"  avviso: {messaggio}"))
        if len(self.avvisi) > 30:
            self.stdout.write(self.style.WARNING(f"  … e altri {len(self.avvisi) - 30} avvisi"))


class Command(BaseCommand):
    help = "Importa i dati (contatti, articoli, documenti…) dal dump SQL di Odoo."

    def add_arguments(self, parser):
        parser.add_argument("dump", help="Percorso del file dump.sql esportato da Odoo.")
        parser.add_argument(
            "--conferma",
            action="store_true",
            help="Esegue davvero lo svuotamento e l'importazione (senza, mostra solo l'anteprima).",
        )

    def handle(self, *args, **opzioni):
        percorso = opzioni["dump"]
        if not os.path.exists(percorso):
            raise CommandError(f"File non trovato: {percorso}")
        inizio = time.monotonic()
        self.stdout.write("Lettura del dump in corso…")
        dati = carica_dump(percorso)
        durata = time.monotonic() - inizio
        righe = sum(len(v) for v in dati.values())
        self.stdout.write(f"Dump letto in {durata:.0f} secondi ({righe} righe utili).")
        importatore = Importatore(dati, self.stdout, self.style)
        if not opzioni["conferma"]:
            importatore.anteprima()
            self.stdout.write(
                "\nNessuna modifica scritta. Lancia di nuovo con --conferma per importare davvero."
            )
            return
        with transaction.atomic():
            importatore.esegui()
        importatore.riepilogo()
