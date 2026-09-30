"""Statistiche di vendita: fatturato e marginalità.

Il «fatturato» è il valore degli ordini cliente consegnati (imponibile, IVA esclusa).
Il «costo» di ogni riga usa il costo unitario fissato alla conferma dell'ordine,
con fallback sul prezzo di acquisto attuale dell'articolo.
"""
from datetime import date
from decimal import Decimal

from django.utils import timezone

from .models import SalesOrder, SalesOrderLine, round2

ZERO = Decimal("0")

PERIOD_MONTH = "mese"
PERIOD_YEAR = "anno"
PERIOD_12M = "12m"
PERIOD_CHOICES = [
    (PERIOD_MONTH, "Mese corrente"),
    (PERIOD_YEAR, "Anno corrente"),
    (PERIOD_12M, "Ultimi 12 mesi"),
]

MONTH_ABBR = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def add_months(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def period_bounds(period):
    today = timezone.localdate()
    if period == PERIOD_MONTH:
        start = today.replace(day=1)
    elif period == PERIOD_12M:
        year, month = add_months(today.year, today.month, -11)
        start = date(year, month, 1)
    else:
        start = today.replace(month=1, day=1)
    return start, today


def line_cost(line):
    cost = line.unit_cost
    if cost is None:
        cost = line.product.purchase_price if line.product_id else ZERO
    return Decimal(cost or 0) * Decimal(line.qty or 0)


def delivered_lines(period):
    start, end = period_bounds(period)
    return SalesOrderLine.objects.filter(
        order__status=SalesOrder.STATUS_DELIVERED,
        order__delivered_at__date__gte=start,
        order__delivered_at__date__lte=end,
    ).select_related("product", "product__main_supplier", "order")


def summary(period):
    revenue = ZERO
    cost = ZERO
    order_ids = set()
    for line in delivered_lines(period):
        revenue += line.line_subtotal
        cost += line_cost(line)
        order_ids.add(line.order_id)
    margin = revenue - cost
    return {
        "period": period,
        "revenue": revenue,
        "cost": cost,
        "margin": margin,
        "margin_pct": round2(margin / revenue * 100) if revenue else ZERO,
        "orders": len(order_ids),
    }


def _group_lines(period, key_func):
    rows = {}
    for line in delivered_lines(period):
        key, label = key_func(line)
        entry = rows.setdefault(key, {"label": label, "revenue": ZERO, "cost": ZERO})
        entry["revenue"] += line.line_subtotal
        entry["cost"] += line_cost(line)
    result = []
    for entry in rows.values():
        entry["margin"] = entry["revenue"] - entry["cost"]
        entry["margin_pct"] = round2(entry["margin"] / entry["revenue"] * 100) if entry["revenue"] else ZERO
        result.append(entry)
    result.sort(key=lambda row: row["margin"], reverse=True)
    return result


def by_product(period):
    def key_func(line):
        if line.product_id:
            return f"p{line.product_id}", line.product.name
        return "none", line.description or "Voci libere"

    return _group_lines(period, key_func)


def by_supplier(period):
    def key_func(line):
        supplier = line.product.main_supplier if line.product_id else None
        if supplier:
            return f"s{supplier.pk}", supplier.name
        return "none", "Senza fornitore"

    return _group_lines(period, key_func)


def monthly_series(months=12):
    """Serie fatturato/margine per gli ultimi N mesi (per i grafici)."""
    today = timezone.localdate()
    start_year, start_month = add_months(today.year, today.month, -(months - 1))
    start = date(start_year, start_month, 1)

    lines = SalesOrderLine.objects.filter(
        order__status=SalesOrder.STATUS_DELIVERED,
        order__delivered_at__date__gte=start,
    ).select_related("product", "order")

    buckets = {}
    for line in lines:
        when = timezone.localtime(line.order.delivered_at).date()
        key = (when.year, when.month)
        entry = buckets.setdefault(key, {"revenue": ZERO, "cost": ZERO})
        entry["revenue"] += line.line_subtotal
        entry["cost"] += line_cost(line)

    labels, revenue, margin = [], [], []
    year, month = start_year, start_month
    for _ in range(months):
        labels.append(f"{MONTH_ABBR[month - 1]} {str(year)[2:]}")
        entry = buckets.get((year, month))
        if entry:
            revenue.append(float(entry["revenue"]))
            margin.append(float(entry["revenue"] - entry["cost"]))
        else:
            revenue.append(0.0)
            margin.append(0.0)
        year, month = add_months(year, month, 1)

    return {"labels": labels, "revenue": revenue, "margin": margin}
