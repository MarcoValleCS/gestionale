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


def render_pdf_cached(chiave, html, timeout=3600):
    """Come ``render_pdf``, ma riusa il PDF finché il documento non cambia.

    Generare un PDF costa 1-3 secondi di CPU piena: senza cache, ogni download
    e ogni invio email rifacevano lo stesso lavoro e accodavano gli altri
    utenti (su 1 vCPU). La chiave deve contenere l'ultima modifica.
    """
    from django.core.cache import cache

    from .cache import cache_attiva

    if not pdf_available():
        return None
    if cache_attiva():
        pdf = cache.get(chiave)
        if pdf:
            return pdf
    pdf = render_pdf(html)
    if pdf and cache_attiva():
        try:
            cache.set(chiave, pdf, timeout)
        except Exception:
            pass
    return pdf


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
