"""Logica di business di vendite: conversioni, conferme, consegne."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement

from .models import Quote, QuoteLine, SalesOrder, SalesOrderLine


def duplicate_quote(quote, user=None):
    """Crea una copia in bozza del preventivo."""
    with transaction.atomic():
        new = Quote.objects.create(
            date=timezone.localdate(),
            valid_until=quote.valid_until,
            customer=quote.customer,
            payment_term=quote.payment_term,
            reference=quote.reference,
            notes=quote.notes,
            terms_text=quote.terms_text,
            status=Quote.STATUS_DRAFT,
            created_by=user,
        )
        for line in quote.lines.all():
            QuoteLine.objects.create(
                quote=new,
                position=line.position,
                product=line.product,
                description=line.description,
                qty=line.qty,
                uom=line.uom,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                vat_rate=line.vat_rate,
            )
        new.recalculate()
        return new


def convert_quote_to_order(quote, user=None):
    """Trasforma un preventivo in ordine cliente."""
    if quote.status == Quote.STATUS_CONVERTED:
        raise ValidationError("Questo preventivo è già stato convertito in ordine.")
    if not quote.lines.exists():
        raise ValidationError("Il preventivo non contiene righe.")

    with transaction.atomic():
        order = SalesOrder.objects.create(
            date=timezone.localdate(),
            customer=quote.customer,
            payment_term=quote.payment_term,
            source_quote=quote,
            reference=quote.reference,
            notes="",
            terms_text=quote.terms_text,
            created_by=user,
        )
        for line in quote.lines.all():
            SalesOrderLine.objects.create(
                order=order,
                position=line.position,
                product=line.product,
                description=line.description,
                qty=line.qty,
                uom=line.uom,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                vat_rate=line.vat_rate,
            )
        order.recalculate()
        quote.status = Quote.STATUS_CONVERTED
        quote.save(update_fields=["status"])
        return order


def confirm_sales_order(order, user=None, replenish=False):
    """Conferma l'ordine e genera gli ordini fornitore per le carenze di magazzino.

    Con ``replenish=True`` vengono riordinati anche gli articoli sotto scorta
    minima (per riportarli almeno alla scorta minima).

    Restituisce ``{"purchase_orders": [...], "without_supplier": [(product, qty), ...]}``.
    """
    if order.status != SalesOrder.STATUS_DRAFT:
        raise ValidationError("Solo gli ordini in bozza possono essere confermati.")

    lines = list(order.lines.select_related("product", "product__main_supplier"))
    if not lines:
        raise ValidationError("L'ordine non contiene righe.")

    # Fabbisogno per articolo (considerando quanto non ancora consegnato)
    needed = {}
    for line in lines:
        product = line.product
        if product is None or not product.is_stock_tracked:
            continue
        remaining = line.qty_remaining
        if remaining <= 0:
            continue
        entry = needed.setdefault(product.pk, {"product": product, "qty": Decimal("0")})
        entry["qty"] += remaining

    # Quantità da ordinare: carenze dell'ordine (+ riordino sotto scorta)
    quantities = {}
    for entry in needed.values():
        product = entry["product"]
        shortage = entry["qty"] - product.total_stock
        if shortage > 0:
            quantities[product.pk] = {"product": product, "qty": shortage}

    if replenish:
        from apps.catalog.models import Product

        low_stock_products = Product.objects.filter(
            active=True, is_stock_tracked=True, min_stock__gt=0, main_supplier__isnull=False
        )
        for product in low_stock_products:
            topup = product.min_stock - product.total_stock
            if topup <= 0:
                continue
            current = quantities.get(product.pk)
            if current is None:
                quantities[product.pk] = {"product": product, "qty": topup}
            elif topup > current["qty"]:
                current["qty"] = topup

    by_supplier = {}
    without_supplier = []
    for entry in quantities.values():
        product = entry["product"]
        supplier = product.main_supplier
        if supplier is None:
            without_supplier.append((product, entry["qty"]))
            continue
        group = by_supplier.setdefault(supplier.pk, {"supplier": supplier, "items": []})
        group["items"].append((product, entry["qty"]))

    from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine

    created = []
    with transaction.atomic():
        # Fissa il costo unitario per il calcolo della marginalità
        for line in lines:
            if line.product_id and line.unit_cost is None:
                line.unit_cost = line.product.purchase_unit_price(line.product.main_supplier)
                line.save(update_fields=["unit_cost"])

        for group in by_supplier.values():
            supplier = group["supplier"]
            lead_days = max((product.supplier_lead_days or 0) for product, _qty in group["items"])
            expected_date = timezone.localdate() + timedelta(days=lead_days) if lead_days else None
            po = PurchaseOrder.objects.create(
                supplier=supplier,
                source_sales_order=order,
                expected_date=expected_date,
                notes=f"Generato automaticamente da ordine cliente {order.number}",
                created_by=user,
            )
            for position, (product, quantity) in enumerate(group["items"], start=1):
                PurchaseOrderLine.objects.create(
                    po=po,
                    position=position,
                    product=product,
                    description=product.name,
                    qty=quantity,
                    uom=product.uom,
                    unit_price=product.purchase_unit_price(supplier),
                    vat_rate=product.purchase_vat,
                )
            po.recalculate()
            created.append(po)

        order.status = SalesOrder.STATUS_CONFIRMED
        order.confirmed_at = timezone.now()
        order.save(update_fields=["status", "confirmed_at"])

    return {"purchase_orders": created, "without_supplier": without_supplier}


def deliver_sales_order(order, user=None, warehouse=None):
    """Segna come consegnato l'ordine e scarica il magazzino. Restituisce la lista errori."""
    if order.status not in {SalesOrder.STATUS_CONFIRMED, SalesOrder.STATUS_DRAFT}:
        raise ValidationError("L'ordine non è in uno stato che consente la consegna.")

    errors = []
    for line in order.lines.select_related("product"):
        remaining = line.qty_remaining
        if remaining <= 0:
            continue
        if line.product is not None and line.product.is_stock_tracked:
            try:
                register_movement(
                    product=line.product,
                    warehouse=warehouse,
                    delta=-remaining,
                    movement_type=StockMovement.TYPE_UNLOAD,
                    user=user,
                    reference=order.number,
                    note=f"Consegna {order.number}",
                )
            except ValidationError as exc:
                errors.append(str(exc))
                continue
        update_fields = ["qty_delivered"]
        if line.product_id and line.unit_cost is None:
            line.unit_cost = line.product.purchase_unit_price(line.product.main_supplier)
            update_fields.append("unit_cost")
        line.qty_delivered = line.qty
        line.save(update_fields=update_fields)

    if order.all_delivered:
        order.status = SalesOrder.STATUS_DELIVERED
        order.delivered_at = timezone.now()
        order.save(update_fields=["status", "delivered_at"])

    return errors


def cancel_sales_order(order, user=None):
    if order.status == SalesOrder.STATUS_DELIVERED:
        raise ValidationError("Un ordine consegnato non può essere annullato.")
    if order.lines.filter(qty_delivered__gt=0).exists():
        raise ValidationError("Alcune righe sono già state consegnate: impossibile annullare.")
    order.status = SalesOrder.STATUS_CANCELLED
    order.save(update_fields=["status"])
    return order
