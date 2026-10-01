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
    lines = [line for line in order.lines.select_related("product") if line.qty_remaining > 0]
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


# --------------------------------------------------------- fatture ricevute
def create_purchase_invoice_from_po(po, user=None, only_received=False):
    lines = list(po.lines.select_related("product"))
    rows = []
    for line in lines:
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
