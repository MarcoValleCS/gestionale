"""Generazione dei PDF (WeasyPrint) e utilità comuni ai documenti stampabili.

Se WeasyPrint non è disponibile (es. Windows senza librerie GTK) le funzioni
restituiscono ``None``: il gestionale continua a funzionare, si stampa dal
browser e l'email parte senza allegato.
"""
import base64
import mimetypes


def pdf_available():
    """True se WeasyPrint è utilizzabile su questo sistema."""
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def render_pdf(html):
    """Trasforma l'HTML del documento in PDF (bytes), oppure None."""
    if not pdf_available():
        return None
    import weasyprint

    return weasyprint.HTML(string=html).write_pdf()


def logo_data_uri():
    """Il logo aziendale come data-URI.

    Serve per i PDF generati fuori dal browser: un normale URL /media/ non
    sarebbe raggiungibile da WeasyPrint.
    """
    from .models import CompanySettings

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
