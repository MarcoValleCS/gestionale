"""Generazione del PDF della fattura (WeasyPrint)."""
from apps.core.pdf import pdf_available, render_pdf  # noqa: F401  (riesportate)


def render_invoice_pdf(invoice):
    """Renderizza la fattura emessa in PDF (bytes) oppure None se non disponibile."""
    from django.template.loader import render_to_string

    from .printing import sales_invoice_print_context

    html = render_to_string("print/document.html", sales_invoice_print_context(invoice))
    return render_pdf(html)
