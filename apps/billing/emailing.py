"""Invio delle fatture emesse via email (con PDF in allegato se disponibile)."""
from apps.core.mailing import email_configured, send_document_email  # noqa: F401  (riesportata)

from .pdf import render_invoice_pdf


def send_invoice_email(invoice, *, to_email, subject, message):
    """Invia la fattura per email. Restituisce True se il PDF è stato allegato."""
    pdf = render_invoice_pdf(invoice)
    return send_document_email(
        to_email=to_email,
        subject=subject,
        message=message,
        attachment=pdf,
        attachment_name=f"Fattura_{invoice.number}.pdf",
    )
