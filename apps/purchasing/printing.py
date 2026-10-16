"""Contesto condiviso per stampa e PDF degli ordini fornitore."""
from django.urls import reverse

from apps.core.models import CompanySettings
from apps.core.pdf import logo_data_uri
from apps.sales.views import build_print_context, fdate


def po_print_context(order, *, back_url=None):
    """Contesto completo per il modello stampabile dell'ordine fornitore."""
    company = CompanySettings.load()
    context = build_print_context(
        order,
        title="Ordine fornitore",
        counterparty=order.supplier,
        counterparty_label="Spett.le fornitore",
        meta_rows=[
            ("Data", fdate(order.date)),
            ("Consegna prevista", fdate(order.expected_date)),
            ("Pagamento", order.payment_term.name if order.payment_term else ""),
            (
                "Nostro riferimento",
                order.source_sales_order.number if order.source_sales_order else order.number,
            ),
            ("Cantiere", str(order.job) if order.job_id else ""),
        ],
        back_url=back_url or reverse("purchasing:po_detail", args=[order.pk]),
        notes=order.notes,
        # stampa essenziale per il fornitore: niente righe di sezione; le
        # colonne mostrano prezzo di listino, sconto applicato e prezzo netto
        show_sections=False,
        show_net_price=True,
        show_signature=False,
    )
    context["company"] = company
    context["logo_src"] = logo_data_uri() or (company.logo.url if company.logo else "")
    context["download_url"] = reverse("purchasing:po_pdf", args=[order.pk])
    return context
