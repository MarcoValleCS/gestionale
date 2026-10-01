"""Invio email dei documenti (fatture, preventivi) con PDF in allegato."""
from django.conf import settings
from django.core.mail import EmailMessage


def email_configured():
    """True se l'invio email è configurato nel file .env."""
    return bool(getattr(settings, "EMAIL_IS_CONFIGURED", False))


def send_document_email(*, to_email, subject, message, attachment=None, attachment_name=""):
    """Invia un documento per email. Restituisce True se il PDF è stato allegato."""
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    if attachment:
        email.attach(attachment_name, attachment, "application/pdf")
    email.send(fail_silently=False)
    return bool(attachment)
