"""Contesti condivisi per stampa, PDF ed email delle fatture."""
from django.urls import reverse

from apps.core.models import CompanySettings
from apps.core.pdf import logo_data_uri
from apps.sales.views import build_print_context, fdate


def sales_invoice_print_context(invoice):
    """Contesto completo per il modello stampabile della fattura emessa."""
    company = CompanySettings.load()
    meta_rows = [
        ("Data", fdate(invoice.date)),
        ("Scadenza", fdate(invoice.due_date)),
        ("Pagamento", invoice.payment_term.name if invoice.payment_term else ""),
        ("Vostro riferimento", invoice.reference),
        ("Cantiere", str(invoice.job) if invoice.job_id else ""),
    ]
    if invoice.kind == invoice.KIND_SAL and invoice.sal_percent is not None:
        meta_rows.append(("Avanzamento lavori", f"{invoice.sal_percent} %"))
    context = build_print_context(
        invoice,
        title=invoice.kind_title,
        counterparty=invoice.customer,
        counterparty_label="Spett.le cliente",
        meta_rows=meta_rows,
        back_url=reverse("billing:salesinvoice_detail", args=[invoice.pk]),
        notes=invoice.notes,
        show_prices=True,
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    return context
