"""Contesti condivisi per stampa, PDF ed email dei preventivi.

Sta qui e non in ``views.py`` per poter essere usato anche dalla generazione
del PDF: ``pdf.py`` non può importare ``views.py``, perché sarebbe un ciclo.
"""
from django.urls import reverse

from apps.core.models import CompanySettings
from apps.core.pdf import logo_data_uri

from .views import build_print_context, fdate


def quote_print_context(quote, *, back_url=None):
    """Contesto completo per il modello stampabile del preventivo."""
    company = CompanySettings.load()
    context = build_print_context(
        quote,
        title="Preventivo",
        counterparty=quote.customer,
        counterparty_label="Spett.le cliente",
        meta_rows=[
            ("Data", fdate(quote.date)),
            ("Valido fino al", fdate(quote.valid_until)),
            ("Pagamento", quote.payment_term.name if quote.payment_term else ""),
            ("Vostro riferimento", quote.reference),
            ("Cantiere", str(quote.job) if quote.job_id else ""),
        ],
        back_url=back_url or reverse("sales:quote_detail", args=[quote.pk]),
        notes=quote.terms_text,
        show_signature=True,
        signature_label="Per accettazione (data e firma)",
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    return context
