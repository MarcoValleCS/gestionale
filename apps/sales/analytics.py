"""Statistiche di vendita: fatturato e marginalità.

Il «fatturato» è il valore degli ordini cliente consegnati (imponibile, IVA esclusa).
Il «costo» di ogni riga usa il costo unitario fissato alla conferma dell'ordine,
con fallback sul prezzo di acquisto attuale dell'articolo.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.utils import timezone

from .models import DISPLAY_LINE_TYPES, SalesOrder, SalesOrderLine, round2

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
    """Costo della riga (delega alla property del modello, unica implementazione)."""
    return line.line_cost


def delivered_lines(period):
    start, end = period_bounds(period)
    return (
        SalesOrderLine.objects.filter(
            order__status=SalesOrder.STATUS_DELIVERED,
            order__delivered_at__date__gte=start,
            order__delivered_at__date__lte=end,
        )
        .exclude(line_type__in=DISPLAY_LINE_TYPES)
        .select_related("product", "product__main_supplier", "order", "order__customer", "order__job")
    )


def lines_with_shares(period):
    """Righe consegnate con costo e quota di provvigione già calcolati.

    La provvigione è concordata sul documento, non sulla singola riga: ogni
    riga se ne porta la quota proporzionale al proprio imponibile. Così i
    raggruppamenti per articolo o fornitore restano coerenti col totale.
    """
    commission_by_order = {}
    for line in delivered_lines(period):
        order = line.order
        if order.pk not in commission_by_order:
            commission_by_order[order.pk] = order.commission_amount
        order_commission = commission_by_order[order.pk]

        line_revenue = line.line_subtotal
        if order_commission and order.subtotal:
            share = round2(order_commission * line_revenue / order.subtotal)
        else:
            share = ZERO
        yield line, line_revenue, round2(line_cost(line)), share


def summary(period):
    revenue = ZERO
    cost = ZERO
    commission = ZERO
    order_ids = set()
    for line, line_revenue, row_cost, share in lines_with_shares(period):
        revenue += line_revenue
        cost += row_cost
        commission += share
        order_ids.add(line.order_id)
    # la provvigione erode il margine, come il costo
    revenue = round2(revenue)
    cost = round2(cost)
    commission = round2(commission)
    margin = round2(revenue - cost - commission)
    return {
        "period": period,
        "revenue": revenue,
        "cost": cost,
        "commission": commission,
        "margin": margin,
        "margin_pct": round2(margin / revenue * 100) if revenue else ZERO,
        "margin_before_commission": round2(revenue - cost),
        "orders": len(order_ids),
    }


def _group_lines(period, key_func):
    rows = {}
    for line, line_revenue, row_cost, share in lines_with_shares(period):
        key, label = key_func(line)
        _accumulate(rows, key, label, line_revenue, row_cost, share)
    return _finalize(rows)


def _finalize(rows, limit=None):
    result = list(rows.values())
    for entry in result:
        # la provvigione erode il margine, come il costo
        entry["revenue"] = round2(entry["revenue"])
        entry["cost"] = round2(entry["cost"])
        entry["commission"] = round2(entry["commission"])
        entry["margin"] = round2(entry["revenue"] - entry["cost"] - entry["commission"])
        entry["margin_pct"] = round2(entry["margin"] / entry["revenue"] * 100) if entry["revenue"] else ZERO
    result.sort(key=lambda row: row["margin"], reverse=True)
    return result[:limit] if limit else result


def _accumulate(rows, key, label, revenue, cost, commission=ZERO, quantity=ZERO):
    entry = rows.get(key)
    if entry is None:
        entry = rows[key] = {"label": label, "revenue": ZERO, "cost": ZERO, "commission": ZERO, "quantity": ZERO}
    entry["revenue"] += revenue
    entry["cost"] += cost
    entry["commission"] += commission
    entry["quantity"] += quantity


def breakdowns(period, limit=10):
    """Fatturato, margine e raggruppamenti in un unico passaggio sulle righe.

    Le singole funzioni (``summary``, ``by_product``…) scorrono ciascuna le
    stesse righe: usarle tutte insieme costa cinque query pesanti. Qui le righe
    vengono lette una volta sola e ripartite fra tutti i raggruppamenti.
    """
    revenue = ZERO
    cost = ZERO
    commission_total = ZERO
    order_ids = set()
    product_rows, supplier_rows, customer_rows, job_rows = {}, {}, {}, {}
    # provvigione per ordine, per ripartirla sulle righe in proporzione
    commission_by_order = {}

    for line in delivered_lines(period):
        order = line.order
        line_revenue = line.line_subtotal
        row_cost = line_cost(line)

        if order.pk not in commission_by_order:
            commission_by_order[order.pk] = order.commission_amount
        order_commission = commission_by_order[order.pk]
        # la provvigione è sul documento: ogni riga se ne porta la quota
        # proporzionale al proprio imponibile
        if order_commission and order.subtotal:
            row_commission = round2(order_commission * line_revenue / order.subtotal)
        else:
            row_commission = ZERO

        revenue += line_revenue
        cost += row_cost
        commission_total += row_commission
        order_ids.add(line.order_id)

        if line.product_id:
            _accumulate(product_rows, f"p{line.product_id}", line.product.name, line_revenue, row_cost, row_commission, line.qty)
            supplier = line.product.main_supplier
        else:
            _accumulate(product_rows, "none", line.description or "Voci libere", line_revenue, row_cost, row_commission, line.qty)
            supplier = None

        if supplier:
            _accumulate(supplier_rows, f"s{supplier.pk}", supplier.name, line_revenue, row_cost, row_commission, line.qty)
        else:
            _accumulate(supplier_rows, "none", "Senza fornitore", line_revenue, row_cost, row_commission, line.qty)

        customer = order.customer
        _accumulate(customer_rows, f"c{customer.pk}", customer.name, line_revenue, row_cost, row_commission, line.qty)

        job = order.job if order.job_id else None
        if job:
            _accumulate(job_rows, f"j{job.pk}", f"{job.code} – {job.name}", line_revenue, row_cost, row_commission, line.qty)
        else:
            _accumulate(job_rows, "none", "Senza cantiere", line_revenue, row_cost, row_commission, line.qty)

    margin = revenue - cost - commission_total
    return {
        "summary": {
            "period": period,
            "revenue": revenue,
            "cost": cost,
            "commission": commission_total,
            "margin": margin,
            "margin_pct": round2(margin / revenue * 100) if revenue else ZERO,
            "margin_before_commission": revenue - cost,
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


# ------------------------------------------------------------- provvigioni
STATO_CONSEGNATI = (SalesOrder.STATUS_DELIVERED,)
STATO_CONFERMATI = (SalesOrder.STATUS_CONFIRMED,)
STATO_TUTTI = (SalesOrder.STATUS_CONFIRMED, SalesOrder.STATUS_DELIVERED)


def month_label(year, month):
    return f"{MONTH_ABBR[month - 1]} {year}"


def commission_report(year=None, month=None, statuses=STATO_TUTTI):
    """Provvigioni da riconoscere nel mese, raggruppate per beneficiario.

    Un ordine entra nel mese in cui la provvigione matura: il mese della
    consegna per gli ordini consegnati, il mese dell'ordine per gli altri
    (che sono ancora in lavorazione).
    """
    from django.db.models import Q

    today = timezone.localdate()
    year = int(year or today.year)
    month = int(month or today.month)
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])

    ordini = (
        SalesOrder.objects.filter(
            status__in=statuses,
            commission_contact__isnull=False,
            commission_pct__gt=0,
        )
        .filter(
            Q(delivered_at__isnull=False, delivered_at__date__gte=start, delivered_at__date__lte=end)
            | Q(delivered_at__isnull=True, date__gte=start, date__lte=end)
        )
        .select_related("commission_contact", "customer")
        .order_by("date", "number")
    )

    righe = {}
    for ordine in ordini:
        voce = righe.setdefault(
            ordine.commission_contact_id,
            {
                "contact": ordine.commission_contact,
                "orders": [],
                "revenue": ZERO,
                "commission": ZERO,
                "paid": ZERO,
                "pending": ZERO,
            },
        )
        importo = ordine.commission_amount
        consegnato = ordine.delivered_at is not None
        voce["orders"].append(
            {
                "order": ordine,
                "revenue": ordine.subtotal,
                "commission": importo,
                "delivered": consegnato,
                "when": timezone.localtime(ordine.delivered_at).date() if consegnato else ordine.date,
            }
        )
        voce["revenue"] += ordine.subtotal
        voce["commission"] += importo
        if consegnato:
            voce["paid"] += importo
        else:
            voce["pending"] += importo

    result = list(righe.values())
    for voce in result:
        voce["revenue"] = round2(voce["revenue"])
        voce["commission"] = round2(voce["commission"])
        voce["paid"] = round2(voce["paid"])
        voce["pending"] = round2(voce["pending"])
        voce["orders"].sort(key=lambda riga: riga["when"])
    result.sort(key=lambda voce: voce["commission"], reverse=True)

    return {
        "year": year,
        "month": month,
        "label": month_label(year, month),
        "rows": result,
        "total_revenue": round2(sum(voce["revenue"] for voce in result)),
        "total_commission": round2(sum(voce["commission"] for voce in result)),
        "total_paid": round2(sum(voce["paid"] for voce in result)),
        "total_pending": round2(sum(voce["pending"] for voce in result)),
        "orders_count": sum(len(voce["orders"]) for voce in result),
    }


def commission_year(year=None, statuses=STATO_TUTTI):
    """Totale provvigioni dell'anno per beneficiario (riepilogo)."""
    today = timezone.localdate()
    year = int(year or today.year)
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    from django.db.models import Q

    ordini = (
        SalesOrder.objects.filter(
            status__in=statuses,
            commission_contact__isnull=False,
            commission_pct__gt=0,
        )
        .filter(
            Q(delivered_at__isnull=False, delivered_at__date__gte=start, delivered_at__date__lte=end)
            | Q(delivered_at__isnull=True, date__gte=start, date__lte=end)
        )
        .select_related("commission_contact")
    )

    riepilogo = {}
    for ordine in ordini:
        voce = riepilogo.setdefault(
            ordine.commission_contact_id,
            {"contact": ordine.commission_contact, "orders": 0, "revenue": ZERO, "commission": ZERO},
        )
        voce["orders"] += 1
        voce["revenue"] += ordine.subtotal
        voce["commission"] += ordine.commission_amount

    righe = list(riepilogo.values())
    for voce in righe:
        voce["revenue"] = round2(voce["revenue"])
        voce["commission"] = round2(voce["commission"])
    righe.sort(key=lambda voce: voce["commission"], reverse=True)
    return righe


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

    lines = (
        SalesOrderLine.objects.filter(
            order__status=SalesOrder.STATUS_DELIVERED,
            order__delivered_at__date__gte=start,
            order__delivered_at__date__lte=end,
        )
        .exclude(line_type__in=DISPLAY_LINE_TYPES)
        .select_related("product", "order")
    )

    buckets = {}
    commission_by_order = {}
    for line in lines:
        order = line.order
        when = timezone.localtime(order.delivered_at).date()
        key = (when.year, when.month)
        entry = buckets.setdefault(key, {"revenue": ZERO, "cost": ZERO, "commission": ZERO})
        line_revenue = line.line_subtotal

        if order.pk not in commission_by_order:
            commission_by_order[order.pk] = order.commission_amount
        order_commission = commission_by_order[order.pk]
        if order_commission and order.subtotal:
            entry["commission"] += round2(order_commission * line_revenue / order.subtotal)

        entry["revenue"] += line_revenue
        entry["cost"] += line_cost(line)

    labels, revenue, margin, rows = [], [], [], []
    year, month = start_year, start_month
    for _ in range(months):
        label = f"{MONTH_ABBR[month - 1]} {str(year)[2:]}"
        labels.append(label)
        entry = buckets.get((year, month))
        month_revenue = entry["revenue"] if entry else ZERO
        month_margin = (entry["revenue"] - entry["cost"] - entry["commission"]) if entry else ZERO
        revenue.append(float(month_revenue))
        margin.append(float(month_margin))
        rows.append(
            {
                "label": label,
                "revenue": round2(month_revenue),
                "cost": round2(entry["cost"]) if entry else ZERO,
                "margin": round2(month_margin),
                "commission": round2(entry["commission"]) if entry else ZERO,
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
