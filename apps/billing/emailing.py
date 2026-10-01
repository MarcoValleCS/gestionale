"""Invio delle fatture emesse via email (con PDF in allegato se disponibile)."""
from django.conf import settings
from django.core.mail import EmailMessage

from .pdf import render_invoice_pdf


def email_configured():
    return bool(getattr(settings, "EMAIL_IS_CONFIGURED", False))


def send_invoice_email(invoice, *, to_email, subject, message):
    """Invia la fattura per email. Restituisce True se il PDF è stato allegato."""
    pdf = render_invoice_pdf(invoice)
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    if pdf:
        email.attach(f"Fattura_{invoice.number}.pdf", pdf, "application/pdf")
    email.send(fail_silently=False)
    return bool(pdf)
