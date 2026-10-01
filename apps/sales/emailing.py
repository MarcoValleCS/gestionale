"""Invio dei preventivi via email (con PDF in allegato se disponibile)."""
from apps.core.mailing import email_configured, send_document_email  # noqa: F401  (riesportata)

from .pdf import render_quote_pdf


def send_quote_email(quote, *, to_email, subject, message):
    """Invia il preventivo per email. Restituisce True se il PDF è stato allegato."""
    pdf = render_quote_pdf(quote)
    return send_document_email(
        to_email=to_email,
        subject=subject,
        message=message,
        attachment=pdf,
        attachment_name=f"Preventivo_{quote.number}.pdf",
    )
