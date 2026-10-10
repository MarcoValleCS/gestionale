"""Generazione dei PDF di preventivi e ordini (WeasyPrint)."""


def _chiave(documento, prefisso):
    modificato = getattr(documento, "updated_at", "") or ""
    return f"pdf_{prefisso}_{documento.pk}_{modificato}"


def render_quote_pdf(quote):
    """Renderizza il preventivo in PDF (bytes) oppure None se non disponibile."""
    from django.template.loader import render_to_string

    from apps.core.pdf import render_pdf_cached

    from .printing import quote_print_context

    html = render_to_string("print/document.html", quote_print_context(quote))
    return render_pdf_cached(_chiave(quote, "preventivo"), html)


def render_order_pdf(order):
    """Renderizza la conferma d'ordine in PDF (bytes) oppure None se non disponibile."""
    from django.template.loader import render_to_string

    from apps.core.pdf import render_pdf_cached

    from .printing import order_print_context

    html = render_to_string("print/document.html", order_print_context(order))
    return render_pdf_cached(_chiave(order, "ordine"), html)
