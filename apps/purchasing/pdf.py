"""Generazione del PDF dell'ordine fornitore (WeasyPrint)."""
from django.template.loader import render_to_string

from apps.core.pdf import render_pdf

from .printing import po_print_context


def render_po_pdf(order):
    """Renderizza l'ordine fornitore in PDF (bytes) oppure None se non disponibile."""
    html = render_to_string("print/document.html", po_print_context(order))
    return render_pdf(html)
