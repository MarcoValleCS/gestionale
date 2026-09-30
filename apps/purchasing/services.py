"""Servizi di acquisti: variazioni listino e ricezione merci."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement

from .models import PriceListAdjustment, PurchaseOrder, PurchaseOrderLine, round4


def apply_pricelist_adjustment(pricelist, percent, user=None):
    """Applica una variazione percentuale a tutte le voci del listino.

    ``percent`` positivo aumenta i prezzi, negativo li diminuisce.
    """
    percent = Decimal(str(percent))
    if percent == 0:
        raise ValidationError("La variazione percentuale non può essere zero.")
    if percent <= -100:
        raise ValidationError("La variazione non può essere inferiore o uguale a -100%.")

    factor = 1 + percent / 100
    items = list(pricelist.items.select_related("product"))
    if not items:
        raise ValidationError("Il listino non contiene articoli da aggiornare.")

    with transaction.atomic():
        for item in items:
            item.price = round4(Decimal(item.price or 0) * factor)
            item.save(update_fields=["price", "updated_at"])
        adjustment = PriceListAdjustment.objects.create(
            pricelist=pricelist,
            percent=percent,
            items_count=len(items),
            applied_by=user,
        )
    return adjustment


def receive_purchase_order(po, quantities, user=None, warehouse=None):
    """Registra la ricezione merce per le righe indicate.

    ``quantities``: dict {line_id: qty}. Restituisce (righe_ricevute, errori).
    """
    received_lines = []
    errors = []
    for line in po.lines.select_related("product"):
        raw = quantities.get(str(line.pk))
        if raw in (None, ""):
            continue
        try:
            qty = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            errors.append(f"Quantità non valida per «{line.description}».")
            continue
        if qty <= 0:
            continue
        if qty > line.qty_remaining:
            errors.append(f"«{line.description}»: ricevuti {qty} ma ne mancano solo {line.qty_remaining}.")
            continue

        with transaction.atomic():
            if line.product is not None and line.product.is_stock_tracked:
                register_movement(
                    product=line.product,
                    warehouse=warehouse,
                    delta=qty,
                    movement_type=StockMovement.TYPE_LOAD,
                    user=user,
                    reference=po.number,
                    note=f"Ricezione {po.number}",
                    unit_cost=line.unit_cost,
                )
            line.qty_received = line.qty_received + qty
            line.save(update_fields=["qty_received"])
        received_lines.append(line)

    if received_lines:
        if po.all_received:
            po.status = PurchaseOrder.STATUS_RECEIVED
        else:
            po.status = PurchaseOrder.STATUS_PARTIAL
        po.save(update_fields=["status"])

    return received_lines, errors


def cancel_purchase_order(po, user=None):
    if po.status == PurchaseOrder.STATUS_RECEIVED:
        raise ValidationError("Un ordine già ricevuto non può essere annullato.")
    if po.lines.filter(qty_received__gt=0).exists():
        raise ValidationError("Alcune righe sono già state ricevute: impossibile annullare.")
    po.status = PurchaseOrder.STATUS_CANCELLED
    po.save(update_fields=["status"])
    return po
