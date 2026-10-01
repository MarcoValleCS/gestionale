"""Generazione del PDF della fattura (WeasyPrint).

Se WeasyPrint non è disponibile (es. Windows senza librerie GTK) le funzioni
restituiscono ``None`` e il gestionale continua a funzionare: si può stampare
il PDF dal browser oppure inviare l'email senza allegato.
"""


def pdf_available():
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def render_invoice_pdf(invoice):
    """Renderizza la fattura emessa in PDF (bytes) oppure None se non disponibile."""
    if not pdf_available():
        return None

    from django.template.loader import render_to_string

    from .printing import sales_invoice_print_context

    html = render_to_string("print/document.html", sales_invoice_print_context(invoice))
    import weasyprint

    return weasyprint.HTML(string=html).write_pdf()
