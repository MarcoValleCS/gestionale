"""Contesti condivisi per stampa, PDF ed email di preventivi e ordini.

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
        # lo sconto è una trattativa interna: al cliente va il prezzo già scontato
        show_discount=False,
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    context["download_url"] = reverse("sales:quote_pdf", args=[quote.pk])
    return context


def order_print_context(order, *, back_url=None):
    """Contesto completo per il modello stampabile della conferma d'ordine."""
    company = CompanySettings.load()
    context = build_print_context(
        order,
        title="Conferma d'ordine",
        counterparty=order.customer,
        counterparty_label="Spett.le cliente",
        meta_rows=[
            ("Data", fdate(order.date)),
            ("Consegna prevista", fdate(order.expected_date)),
            ("Pagamento", order.payment_term.name if order.payment_term else ""),
            ("Vostro riferimento", order.reference),
            ("Cantiere", str(order.job) if order.job_id else ""),
        ],
        back_url=back_url or reverse("sales:order_detail", args=[order.pk]),
        notes=order.terms_text,
        show_signature=True,
        signature_label="Conferma d'ordine (data e firma)",
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    context["download_url"] = reverse("sales:order_pdf", args=[order.pk])
    return context
