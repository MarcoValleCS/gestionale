"""Generazione del PDF della fattura (WeasyPrint)."""
from apps.core.pdf import pdf_available, render_pdf, render_pdf_cached  # noqa: F401  (riesportate)


def render_invoice_pdf(invoice):
    """Renderizza la fattura emessa in PDF (bytes) oppure None se non disponibile."""
    from django.template.loader import render_to_string

    from .printing import sales_invoice_print_context

    modificato = getattr(invoice, "updated_at", "") or ""
    html = render_to_string("print/document.html", sales_invoice_print_context(invoice))
    return render_pdf_cached(f"pdf_fattura_{invoice.pk}_{modificato}", html)
