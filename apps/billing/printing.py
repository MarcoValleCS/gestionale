"""Contesti condivisi per stampa, PDF ed email delle fatture."""
import base64
import mimetypes

from django.urls import reverse

from apps.core.models import CompanySettings
from apps.sales.views import build_print_context, fdate


def logo_data_uri():
    """Il logo aziendale come data-URI (per PDF renderizzati fuori dal browser)."""
    company = CompanySettings.load()
    if not company.logo:
        return ""
    try:
        with company.logo.open("rb") as handle:
            data = handle.read()
        mime = mimetypes.guess_type(company.logo.name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ""


def sales_invoice_print_context(invoice):
    """Contesto completo per il modello stampabile della fattura emessa."""
    company = CompanySettings.load()
    context = build_print_context(
        invoice,
        title="Fattura",
        counterparty=invoice.customer,
        counterparty_label="Spett.le cliente",
        meta_rows=[
            ("Data", fdate(invoice.date)),
            ("Scadenza", fdate(invoice.due_date)),
            ("Pagamento", invoice.payment_term.name if invoice.payment_term else ""),
            ("Vostro riferimento", invoice.reference),
            ("Cantiere", str(invoice.job) if invoice.job_id else ""),
        ],
        back_url=reverse("billing:salesinvoice_detail", args=[invoice.pk]),
        notes=invoice.notes,
        show_prices=True,
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    return context
