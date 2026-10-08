"""Flussi di lavoro: DDT (scarico magazzino) e fatture emesse/ricevute."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement
from apps.sales.models import SalesOrder

from .models import (
    DeliveryNote,
    DeliveryNoteLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)


def _due_date(date, payment_term):
    if payment_term is None:
        return None
    return date + timedelta(days=payment_term.days or 0)


# --------------------------------------------------------------------- DDT
def create_delivery_note_from_order(order, user=None):
    """Crea una bozza di DDT con le quantità non ancora consegnate dell'ordine."""
    if order.status == SalesOrder.STATUS_CANCELLED:
        raise ValidationError("L'ordine è annullato.")
    lines = [line for line in order.lines.select_related("product") if not line.is_display and line.qty_remaining > 0]
    if not lines:
        raise ValidationError("Niente da consegnare: tutte le righe risultano già consegnate.")

    with transaction.atomic():
        note = DeliveryNote.objects.create(
            customer=order.customer,
            job=order.job,
            source_order=order,
            destination=order.job.full_address if order.job_id else "",
            created_by=user,
        )
        for position, line in enumerate(lines, start=1):
            DeliveryNoteLine.objects.create(
                delivery_note=note,
                position=position,
                section=line.section,
                product=line.product,
                description=line.description,
                qty=line.qty_remaining,
                uom=line.uom,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                vat_rate=line.vat_rate,
                source_order_line=line,
            )
    return note


def issue_delivery_note(note, user=None, warehouse=None):
    """Emette il DDT: scarica il magazzino e aggiorna l'ordine collegato."""
    if note.status != DeliveryNote.STATUS_DRAFT:
        raise ValidationError("Solo i DDT in bozza possono essere emessi.")
    if not note.lines.exists():
        raise ValidationError("Il DDT non contiene righe.")

    errors = []
    for line in note.lines.select_related("product", "source_order_line"):
        line_qty = Decimal(line.qty or 0)
        if line_qty <= 0:
            continue
        if line.product is not None and line.product.is_stock_tracked:
            try:
                register_movement(
                    product=line.product,
                    warehouse=warehouse,
                    delta=-line_qty,
                    movement_type=StockMovement.TYPE_UNLOAD,
                    user=user,
                    reference=note.number,
                    note=f"DDT {note.number}",
                )
            except ValidationError as exc:
                errors.append(str(exc))
                continue
        if line.source_order_line_id:
            order_line = line.source_order_line
            new_delivered = min(order_line.qty, order_line.qty_delivered + line_qty)
            if new_delivered != order_line.qty_delivered:
                order_line.qty_delivered = new_delivered
                order_line.save(update_fields=["qty_delivered"])

    note.status = DeliveryNote.STATUS_ISSUED
    note.issued_at = timezone.now()
    note.save(update_fields=["status", "issued_at"])

    if note.source_order_id:
        order = note.source_order
        if order.all_delivered and order.status != SalesOrder.STATUS_DELIVERED:
            order.status = SalesOrder.STATUS_DELIVERED
            order.delivered_at = timezone.now()
            order.save(update_fields=["status", "delivered_at"])

    return errors


def cancel_delivery_note(note):
    if note.status != DeliveryNote.STATUS_DRAFT:
        raise ValidationError("Un DDT emesso non può essere annullato: crea una nota di reso o di credito.")
    note.status = DeliveryNote.STATUS_CANCELLED
    note.save(update_fields=["status"])


# ----------------------------------------------------------- fatture emesse
def _invoice_lines_from(quantity_getter, lines):
    payload = []
    for line in lines:
        if line.is_display:
            continue
        payload.append(
            {
                "position": line.position,
                "section": line.section,
                "product": line.product,
                "description": line.description,
                "qty": quantity_getter(line),
                "uom": line.uom,
                "unit_price": line.unit_price,
                "discount_pct": line.discount_pct,
                "vat_rate": line.vat_rate,
            }
        )
    return payload


def create_sales_invoice_from_order(order, user=None, only_delivered=False):
    lines = list(order.lines.select_related("product"))
    getter = lambda line: (line.qty_delivered if (only_delivered and line.qty_delivered > 0) else line.qty)
    payload = [row for row in _invoice_lines_from(getter, lines) if row["qty"] > 0]
    if not payload:
        raise ValidationError("L'ordine non ha righe fatturabili.")

    with transaction.atomic():
        invoice = SalesInvoice.objects.create(
            customer=order.customer,
            job=order.job,
            source_order=order,
            payment_term=order.payment_term,
            reference=order.reference,
            due_date=_due_date(timezone.localdate(), order.payment_term),
            created_by=user,
        )
        for row in payload:
            SalesInvoiceLine.objects.create(invoice=invoice, **row)
        _apply_advance_storno(order, invoice)
        invoice.recalculate()
    return invoice


def create_sales_invoice_from_delivery_note(note, user=None):
    if note.invoiced:
        raise ValidationError("Questo DDT risulta già fatturato.")
    if not note.lines.exists():
        raise ValidationError("Il DDT non contiene righe.")

    with transaction.atomic():
        invoice = SalesInvoice.objects.create(
            customer=note.customer,
            job=note.job,
            source_order=note.source_order,
            source_delivery_note=note,
            payment_term=note.source_order.payment_term if note.source_order_id else None,
            due_date=_due_date(timezone.localdate(), note.source_order.payment_term if note.source_order_id else None),
            created_by=user,
        )
        for row in _invoice_lines_from(lambda line: line.qty, note.lines.all()):
            SalesInvoiceLine.objects.create(invoice=invoice, **row)
        _apply_advance_storno(note.source_order, invoice)
        invoice.recalculate()
        note.invoiced = True
        note.save(update_fields=["invoiced"])
    return invoice


def issue_sales_invoice(invoice):
    if invoice.status != SalesInvoice.STATUS_DRAFT:
        raise ValidationError("Solo le fatture in bozza possono essere emesse.")
    invoice.status = SalesInvoice.STATUS_ISSUED
    invoice.issued_at = timezone.now()
    invoice.save(update_fields=["status", "issued_at"])


def mark_sales_invoice_sent(invoice):
    if invoice.status not in {SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_DRAFT}:
        raise ValidationError("La fattura non è in uno stato che consente l'invio.")
    invoice.status = SalesInvoice.STATUS_SENT
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "sent_at"])


def mark_sales_invoice_paid(invoice):
    if invoice.status not in {SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT}:
        raise ValidationError("La fattura non risulta emessa/inviata.")
    invoice.status = SalesInvoice.STATUS_PAID
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=["status", "paid_at"])


# ---------------------------------------------- SAL, acconti e saldi (cantieri)
# Stato delle fatture che contano come «fatturato» (le bozze no, ma contano nei
# calcoli dei residui: così non si emettono due SAL per lo stesso avanzamento).
INVOICED_STATUSES = [SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT, SalesInvoice.STATUS_PAID]


def contract_amount_for(job):
    """Valore contratto del cantiere.

    È la somma degli ordini cliente confermati (o consegnati); se il cantiere
    non ha ancora ordini si usa la somma dei preventivi accettati.
    """
    totale = (
        SalesOrder.objects.filter(job=job)
        .exclude(status__in=[SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CANCELLED])
        .aggregate(totale=models.Sum("subtotal"))["totale"]
    )
    if totale:
        return Decimal(totale)
    from apps.sales.models import Quote

    return Decimal(
        Quote.objects.filter(job=job, status=Quote.STATUS_ACCEPTED).aggregate(totale=models.Sum("subtotal"))["totale"] or 0
    )


def job_billing_summary(job):
    """Situazione della fatturazione del cantiere: contratto, fatturato e residuo.

    ``committed`` comprende anche le bozze: serve a non emettere due volte lo
    stesso avanzamento. ``residual`` è quanto resta da fatturare.
    """
    documenti = list(
        SalesInvoice.objects.filter(job=job).exclude(status=SalesInvoice.STATUS_CANCELLED).order_by("-date", "-pk")
    )
    per_tipo = {chiave: Decimal("0") for chiave, _ in SalesInvoice.KIND_CHOICES}
    committed = Decimal("0")
    for documento in documenti:
        committed += Decimal(documento.subtotal or 0)
        if documento.status in INVOICED_STATUSES:
            per_tipo[documento.kind] += Decimal(documento.subtotal or 0)
    contract = contract_amount_for(job)
    ultimo_sal = max((d.sal_number or 0 for d in documenti if d.kind == SalesInvoice.KIND_SAL), default=0)
    return {
        "contract": contract,
        "advances": per_tipo[SalesInvoice.KIND_ADVANCE],
        "sal": per_tipo[SalesInvoice.KIND_SAL],
        "balance": per_tipo[SalesInvoice.KIND_BALANCE],
        "invoices": per_tipo[SalesInvoice.KIND_INVOICE],
        "invoiced": sum(per_tipo.values(), Decimal("0")),
        "committed": committed,
        "residual": contract - committed,
        "next_sal_number": ultimo_sal + 1,
        "documents": documenti,
        "drafts": sum(1 for d in documenti if d.status == SalesInvoice.STATUS_DRAFT),
    }


def _vat_rate_for_job(job):
    """Aliquota IVA più usata nelle righe degli ordini del cantiere (o 22%)."""
    from apps.core.models import VatRate
    from apps.sales.models import SalesOrderLine

    riga = (
        SalesOrderLine.objects.filter(order__job=job)
        .exclude(order__status__in=[SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CANCELLED])
        .exclude(vat_rate__isnull=True)
        .values("vat_rate")
        .annotate(quante=models.Count("pk"))
        .order_by("-quante")
        .first()
    )
    if riga:
        aliquota = VatRate.objects.filter(pk=riga["vat_rate"]).first()
        if aliquota:
            return aliquota
    return VatRate.objects.filter(code="22").first() or VatRate.objects.first()


def create_job_invoice(job, kind, *, percent=None, amount=None, user=None):
    """Crea in bozza un acconto, un SAL o il saldo di un cantiere.

    L'importo è sempre «al netto di quanto già fatturato» (bozze comprese): la
    somma di acconti, SAL e saldi non supera il valore del contratto.
    """
    from apps.core.rounding import round2

    if kind not in {SalesInvoice.KIND_ADVANCE, SalesInvoice.KIND_SAL, SalesInvoice.KIND_BALANCE}:
        raise ValidationError("Tipo di documento non valido per un cantiere.")
    if job.customer_id is None:
        raise ValidationError("Il cantiere non ha un cliente.")

    summary = job_billing_summary(job)
    contract = summary["contract"]
    residuo = contract - summary["committed"]
    percentuale = Decimal(percent) if percent is not None else None

    sal_number = None
    if kind == SalesInvoice.KIND_ADVANCE:
        importo = Decimal(amount) if amount is not None else None
        if importo is None and percentuale:
            importo = round2(contract * percentuale / 100)
        if not importo or importo <= 0:
            raise ValidationError("Indica l'importo o la percentuale dell'acconto.")
        importo = round2(importo)
        descrizione = f"Acconto su contratto – {job.name}"
    elif kind == SalesInvoice.KIND_SAL:
        if contract <= 0:
            raise ValidationError("Il cantiere non ha un valore contratto: conferma un ordine prima di emettere un SAL.")
        if percentuale is None or percentuale <= 0 or percentuale > 100:
            raise ValidationError("Indica la percentuale di avanzamento (fra 0 e 100).")
        sal_number = summary["next_sal_number"]
        obiettivo = round2(contract * percentuale / 100)
        importo = round2(obiettivo - summary["committed"])
        if importo <= 0:
            raise ValidationError(
                f"L'avanzamento al {percentuale}% risulta già fatturato: non c'è nulla da emettere."
            )
        descrizione = (
            f"SAL n. {sal_number} – avanzamento lavori al {percentuale}% (al netto di quanto già fatturato)"
        )
    else:
        importo = round2(residuo)
        if importo <= 0:
            raise ValidationError("Non resta nulla da saldare: il contratto risulta già fatturato.")
        descrizione = f"Saldo lavori – {job.name}"

    iva = _vat_rate_for_job(job)
    ordine = (
        job.sales_orders.exclude(status__in=[SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CANCELLED])
        .order_by("-date", "-pk")
        .first()
    )
    pagamento = (ordine.payment_term if ordine else None) or job.customer.payment_term
    oggi = timezone.localdate()

    with transaction.atomic():
        invoice = SalesInvoice.objects.create(
            customer=job.customer,
            job=job,
            kind=kind,
            sal_number=sal_number,
            sal_percent=percentuale if kind in {SalesInvoice.KIND_ADVANCE, SalesInvoice.KIND_SAL} else None,
            contract_amount=contract,
            payment_term=pagamento,
            due_date=_due_date(oggi, pagamento),
            created_by=user,
        )
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            position=1,
            description=descrizione[:300],
            qty=Decimal("1"),
            unit_price=importo,
            vat_rate=iva,
        )
        invoice.recalculate()
    return invoice


# ------------------------------------------- acconti e resto su un ordine
def order_billing_summary(order):
    """Fatturazione dell'ordine: totale, acconti, fatturato e resto da fatturare."""
    documenti = list(
        SalesInvoice.objects.filter(source_order=order).exclude(status=SalesInvoice.STATUS_CANCELLED).order_by("-date", "-pk")
    )
    per_tipo = {chiave: Decimal("0") for chiave, _ in SalesInvoice.KIND_CHOICES}
    committed = Decimal("0")
    for documento in documenti:
        committed += Decimal(documento.subtotal or 0)
        if documento.status in INVOICED_STATUSES:
            per_tipo[documento.kind] += Decimal(documento.subtotal or 0)
    totale = Decimal(order.subtotal or 0)
    return {
        "total": totale,
        "advances": per_tipo[SalesInvoice.KIND_ADVANCE],
        "invoiced": sum(per_tipo.values(), Decimal("0")),
        "committed": committed,
        "residual": totale - committed,
        "advance_remaining": advance_pool_summary(order)["remaining"],
        "documents": documenti,
        "drafts": sum(1 for d in documenti if d.status == SalesInvoice.STATUS_DRAFT),
    }


def _vat_rate_for_order(order):
    """Aliquota IVA più usata nelle righe dell'ordine (o 22%)."""
    from apps.core.models import VatRate

    riga = (
        order.lines.filter(product__isnull=False)
        .exclude(vat_rate__isnull=True)
        .values("vat_rate")
        .annotate(quante=models.Count("pk"))
        .order_by("-quante")
        .first()
    )
    if riga:
        aliquota = VatRate.objects.filter(pk=riga["vat_rate"]).first()
        if aliquota:
            return aliquota
    return VatRate.objects.filter(code="22").first() or VatRate.objects.first()


def advance_pool_summary(order):
    """Acconto fisso da scalare: versato, già scalato e residuo per aliquota.

    Fanno monte solo le righe «a corpo» (senza articolo) delle fatture di
    acconto non annullate; gli acconti in percentuale hanno righe articolo
    scalate e non alimentano il monte. Lo scalato è la somma delle righe di
    storno (negative) nelle altre fatture dell'ordine.
    """
    from apps.core.rounding import round2

    versato = {}
    scalato = {}
    aliquote = {}
    fatture = (
        SalesInvoice.objects.filter(source_order=order)
        .exclude(status=SalesInvoice.STATUS_CANCELLED)
        .prefetch_related("lines__vat_rate")
    )
    for fattura in fatture:
        for riga in fattura.lines.all():
            if riga.is_display:
                continue
            quota = aliquote.setdefault(
                riga.vat_rate_id, {"vat_rate": riga.vat_rate, "versato": Decimal("0"), "scalato": Decimal("0")}
            )
            if riga.is_advance_deduction:
                quota["scalato"] += riga.line_subtotal
            elif fattura.kind == SalesInvoice.KIND_ADVANCE and riga.product_id is None:
                quota["versato"] += riga.line_subtotal
    per_vat = []
    residuo_totale = Decimal("0")
    for quota in aliquote.values():
        # lo storno è negativo: lo scalato effettivo è il suo valore assoluto
        residuo = round2(quota["versato"] + quota["scalato"])
        if residuo < 0:
            residuo = Decimal("0")
        if quota["versato"] > 0:
            per_vat.append((quota["vat_rate"], residuo))
            residuo_totale += residuo
    return {"remaining": round2(residuo_totale), "per_vat": per_vat}


def _apply_advance_storno(order, invoice):
    """Scala l'acconto fisso residuo dalle merci in fattura (storno per aliquota).

    Aggiunge una riga negativa «Storno acconto» per ogni aliquota presente
    nelle merci, fino a esaurire il residuo. Restituisce l'importo scalato.
    """
    from apps.core.rounding import round2

    if order is None or invoice.kind == SalesInvoice.KIND_ADVANCE:
        return Decimal("0")
    residui = {getattr(iva, "pk", None): (iva, residuo) for iva, residuo in advance_pool_summary(order)["per_vat"]}
    if not any(residuo > 0 for _, residuo in residui.values()):
        return Decimal("0")
    basi = {}
    posizione = 0
    for riga in invoice.lines.all():
        posizione = max(posizione, riga.position or 0)
        if riga.is_display or riga.is_advance_deduction:
            continue
        chiave = riga.vat_rate_id
        base = basi.setdefault(chiave, [riga.vat_rate, Decimal("0")])
        base[1] += riga.line_subtotal
    scalato = Decimal("0")
    for chiave, (iva, base) in basi.items():
        residuo = residui.get(chiave, (None, Decimal("0")))[1]
        quota = round2(min(residuo, base))
        if quota <= 0:
            continue
        posizione += 1
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            position=posizione,
            description=f"Storno acconto ordine {order.number}"[:300],
            qty=Decimal("1"),
            unit_price=-quota,
            vat_rate=iva,
            is_advance_deduction=True,
        )
        scalato += quota
    if scalato > 0:
        invoice.recalculate()
    return scalato


def _order_lines_scaled(order, ratio):
    """Righe dell'ordine ridotte alla percentuale indicata (quantità)."""
    from decimal import ROUND_HALF_UP

    payload = []
    for line in order.lines.select_related("product"):
        if line.is_display:
            continue
        qty = Decimal(line.qty or 0)
        prezzo = Decimal(line.unit_price or 0)
        if qty == 0:
            continue
        nuova_qty = (qty * ratio).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        nuovo_prezzo = prezzo
        if nuova_qty <= 0:
            # quantità troppo piccola per essere ridotta: si riduce il prezzo
            nuova_qty = Decimal("1")
            nuovo_prezzo = (prezzo * ratio).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        payload.append(
            {
                "position": line.position,
                "section": line.section,
                "product": line.product,
                "description": line.description,
                "qty": nuova_qty,
                "uom": line.uom,
                "unit_price": nuovo_prezzo,
                "discount_pct": line.discount_pct,
                "vat_rate": line.vat_rate,
            }
        )
    return payload


def _create_order_linked_invoice(order, kind, payload, *, percent=None, user=None):
    invoice = SalesInvoice.objects.create(
        customer=order.customer,
        job=order.job,
        source_order=order,
        kind=kind,
        sal_percent=percent,
        contract_amount=Decimal(order.subtotal or 0),
        payment_term=order.payment_term,
        reference=order.reference,
        due_date=_due_date(timezone.localdate(), order.payment_term),
        created_by=user,
    )
    for row in payload:
        SalesInvoiceLine.objects.create(invoice=invoice, **row)
    invoice.recalculate()
    return invoice


def create_order_advance(order, percent=None, amount=None, user=None):
    """Acconto su un ordine: in percentuale (righe scalate) o a importo fisso.

    Percentuale: le righe sono ridotte alla percentuale indicata (es. ordine
    di 3.000 € con acconto al 30% → fattura di 900 €). Le voci restano quelle
    dell'ordine.
    Importo fisso: una riga «Acconto ordine …» da scalare poi dalle fatture
    delle consegne (es. acconto 1.000 € su ordine di 3.000 €).
    """
    from apps.core.rounding import round2

    summary = order_billing_summary(order)
    if summary["total"] <= 0:
        raise ValidationError("L'ordine non ha un imponibile.")
    if amount is not None:
        importo = round2(Decimal(amount))
        if importo <= 0:
            raise ValidationError("L'importo dell'acconto deve essere positivo.")
        if importo > summary["residual"] + Decimal("0.01"):
            raise ValidationError(
                f"L'acconto di {importo:.2f} € supera quanto resta da fatturare ({summary['residual']:.2f} €)."
            )
        iva = _vat_rate_for_order(order)
        payload = [
            {
                "position": 1,
                "section": "",
                "product": None,
                "description": f"Acconto ordine {order.number}"[:300],
                "qty": Decimal("1"),
                "uom": None,
                "unit_price": importo,
                "discount_pct": Decimal("0"),
                "vat_rate": iva,
            }
        ]
        percentuale = None
    else:
        percentuale = Decimal(percent) if percent is not None else None
        if percentuale is None or percentuale <= 0 or percentuale > 100:
            raise ValidationError("Indica la percentuale dell'acconto (fra 0 e 100) oppure un importo fisso.")
        importo = round2(summary["total"] * percentuale / 100)
        if importo > summary["residual"] + Decimal("0.01"):
            raise ValidationError(
                f"L'acconto del {percentuale}% ({importo:.2f} €) supera quanto resta da fatturare "
                f"({summary['residual']:.2f} €)."
            )
        payload = _order_lines_scaled(order, percentuale / 100)
    if not payload:
        raise ValidationError("L'ordine non ha righe fatturabili.")
    with transaction.atomic():
        return _create_order_linked_invoice(order, SalesInvoice.KIND_ADVANCE, payload, percent=percentuale, user=user)


def create_order_balance(order, user=None):
    """Fattura il resto dell'ordine, riducendo le righe in proporzione."""
    summary = order_billing_summary(order)
    totale = summary["total"]
    residuo = summary["residual"]
    if totale <= 0:
        raise ValidationError("L'ordine non ha un imponibile.")
    if residuo <= 0:
        raise ValidationError("L'ordine risulta già interamente fatturato.")
    payload = _order_lines_scaled(order, residuo / totale)
    if not payload:
        raise ValidationError("L'ordine non ha righe fatturabili.")
    with transaction.atomic():
        invoice = _create_order_linked_invoice(order, SalesInvoice.KIND_BALANCE, payload, user=user)
        _apply_advance_storno(order, invoice)
        invoice.recalculate()
        return invoice


# --------------------------------------------------------- fatture ricevute
def create_purchase_invoice_from_po(po, user=None, only_received=False):
    lines = list(po.lines.select_related("product"))
    rows = []
    for line in lines:
        if line.is_display:
            continue
        qty = line.qty_received if (only_received and line.qty_received > 0) else line.qty
        if qty <= 0:
            continue
        rows.append(
            {
                "position": line.position,
                "section": line.section,
                "product": line.product,
                "description": line.description,
                "qty": qty,
                "uom": line.uom,
                "unit_price": line.unit_price,
                "discount_pct": line.discount_pct,
                "vat_rate": line.vat_rate,
            }
        )
    if not rows:
        raise ValidationError("L'ordine fornitore non ha righe fatturabili.")

    with transaction.atomic():
        invoice = PurchaseInvoice.objects.create(
            supplier=po.supplier,
            job=po.job,
            source_po=po,
            payment_term=po.payment_term,
            due_date=_due_date(timezone.localdate(), po.payment_term),
            created_by=user,
        )
        for row in rows:
            PurchaseInvoiceLine.objects.create(invoice=invoice, **row)
        invoice.recalculate()
    return invoice


def register_purchase_invoice(invoice):
    if invoice.status != PurchaseInvoice.STATUS_DRAFT:
        raise ValidationError("Solo le fatture in bozza possono essere registrate.")
    invoice.status = PurchaseInvoice.STATUS_REGISTERED
    invoice.registered_at = timezone.now()
    invoice.save(update_fields=["status", "registered_at"])


def mark_purchase_invoice_paid(invoice):
    if invoice.status != PurchaseInvoice.STATUS_REGISTERED:
        raise ValidationError("La fattura non risulta registrata (da pagare).")
    invoice.status = PurchaseInvoice.STATUS_PAID
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=["status", "paid_at"])
