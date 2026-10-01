"""Statistiche di vendita: fatturato e marginalità.

Il «fatturato» è il valore degli ordini cliente consegnati (imponibile, IVA esclusa).
Il «costo» di ogni riga usa il costo unitario fissato alla conferma dell'ordine,
con fallback sul prezzo di acquisto attuale dell'articolo.
"""
import calendar
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
    ).select_related("product", "product__main_supplier", "order", "order__customer", "order__job")


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


def _finalize(rows, limit=None):
    result = list(rows.values())
    for entry in result:
        entry["margin"] = entry["revenue"] - entry["cost"]
        entry["margin_pct"] = round2(entry["margin"] / entry["revenue"] * 100) if entry["revenue"] else ZERO
    result.sort(key=lambda row: row["margin"], reverse=True)
    return result[:limit] if limit else result


def _accumulate(rows, key, label, revenue, cost):
    entry = rows.get(key)
    if entry is None:
        entry = rows[key] = {"label": label, "revenue": ZERO, "cost": ZERO}
    entry["revenue"] += revenue
    entry["cost"] += cost


def breakdowns(period, limit=10):
    """Fatturato, margine e raggruppamenti in un unico passaggio sulle righe.

    Le singole funzioni (``summary``, ``by_product``…) scorrono ciascuna le
    stesse righe: usarle tutte insieme costa cinque query pesanti. Qui le righe
    vengono lette una volta sola e ripartite fra tutti i raggruppamenti.
    """
    revenue = ZERO
    cost = ZERO
    order_ids = set()
    product_rows, supplier_rows, customer_rows, job_rows = {}, {}, {}, {}

    for line in delivered_lines(period):
        line_revenue = line.line_subtotal
        row_cost = line_cost(line)
        revenue += line_revenue
        cost += row_cost
        order_ids.add(line.order_id)

        if line.product_id:
            _accumulate(product_rows, f"p{line.product_id}", line.product.name, line_revenue, row_cost)
            supplier = line.product.main_supplier
        else:
            _accumulate(product_rows, "none", line.description or "Voci libere", line_revenue, row_cost)
            supplier = None

        if supplier:
            _accumulate(supplier_rows, f"s{supplier.pk}", supplier.name, line_revenue, row_cost)
        else:
            _accumulate(supplier_rows, "none", "Senza fornitore", line_revenue, row_cost)

        customer = line.order.customer
        _accumulate(customer_rows, f"c{customer.pk}", customer.name, line_revenue, row_cost)

        job = line.order.job if line.order.job_id else None
        if job:
            _accumulate(job_rows, f"j{job.pk}", f"{job.code} – {job.name}", line_revenue, row_cost)
        else:
            _accumulate(job_rows, "none", "Senza cantiere", line_revenue, row_cost)

    margin = revenue - cost
    return {
        "summary": {
            "period": period,
            "revenue": revenue,
            "cost": cost,
            "margin": margin,
            "margin_pct": round2(margin / revenue * 100) if revenue else ZERO,
            "orders": len(order_ids),
        },
        "by_product": _finalize(product_rows, limit),
        "by_supplier": _finalize(supplier_rows, limit),
        "by_customer": _finalize(customer_rows, limit),
        "by_job": _finalize(job_rows, limit),
    }


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


def by_customer(period):
    def key_func(line):
        customer = line.order.customer
        return f"c{customer.pk}", customer.name

    return _group_lines(period, key_func)


def by_job(period):
    def key_func(line):
        job = line.order.job if line.order.job_id else None
        if job:
            return f"j{job.pk}", f"{job.code} – {job.name}"
        return "none", "Senza cantiere"

    return _group_lines(period, key_func)


def monthly_series(months=12, end_offset=0):
    """Serie fatturato/margine per gli ultimi N mesi (per il grafico).

    ``end_offset`` sposta la finestra indietro di N mesi (0 = fino al mese corrente).
    """
    today = timezone.localdate()
    end_year, end_month = add_months(today.year, today.month, -end_offset)
    start_year, start_month = add_months(end_year, end_month, -(months - 1))
    start = date(start_year, start_month, 1)
    if end_offset == 0:
        end = today
    else:
        end = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])

    lines = SalesOrderLine.objects.filter(
        order__status=SalesOrder.STATUS_DELIVERED,
        order__delivered_at__date__gte=start,
        order__delivered_at__date__lte=end,
    ).select_related("product", "order")

    buckets = {}
    for line in lines:
        when = timezone.localtime(line.order.delivered_at).date()
        key = (when.year, when.month)
        entry = buckets.setdefault(key, {"revenue": ZERO, "cost": ZERO})
        entry["revenue"] += line.line_subtotal
        entry["cost"] += line_cost(line)

    labels, revenue, margin, rows = [], [], [], []
    year, month = start_year, start_month
    for _ in range(months):
        label = f"{MONTH_ABBR[month - 1]} {str(year)[2:]}"
        labels.append(label)
        entry = buckets.get((year, month))
        month_revenue = entry["revenue"] if entry else ZERO
        month_margin = (entry["revenue"] - entry["cost"]) if entry else ZERO
        revenue.append(float(month_revenue))
        margin.append(float(month_margin))
        rows.append(
            {
                "label": label,
                "revenue": round2(month_revenue),
                "margin": round2(month_margin),
                "margin_pct": round2(month_margin / month_revenue * 100) if month_revenue else ZERO,
            }
        )
        year, month = add_months(year, month, 1)

    return {
        "labels": labels,
        "revenue": revenue,
        "margin": margin,
        "rows": rows,
        "start_label": labels[0] if labels else "",
        "end_label": labels[-1] if labels else "",
        "months": months,
        "end_offset": end_offset,
    }
