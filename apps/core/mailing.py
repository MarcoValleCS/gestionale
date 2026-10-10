"""Invio email dei documenti (fatture, preventivi) con PDF in allegato.

L'invio vero avviene in background (vedi ``EmailInCoda``): la pagina accoda
e risponde subito, così un server SMTP lento non blocca il gestionale.
"""
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

TENTATIVI_MASSIMI = 3


def email_configured():
    """True se l'invio email è configurato nel file .env."""
    return bool(getattr(settings, "EMAIL_IS_CONFIGURED", False))


def send_document_email(*, to_email, subject, message, attachment=None, attachment_name=""):
    """Invia subito un documento per email. Restituisce True se il PDF è stato allegato.

    Usata solo dal comando di background e nei test: le viste usano
    ``accoda_email`` per non bloccare la pagina.
    """
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


def accoda_email(*, to_email, subject, message, attachment=None, attachment_name="",
                 attachment_type="application/pdf", descrizione="", modello="libera", oggetto_id=None):
    """Mette un'email in coda (un INSERT: millisecondi, niente rete)."""
    from .models import EmailInCoda

    if attachment_name and attachment is None:
        attachment_name = ""
    return EmailInCoda.objects.create(
        to_email=to_email,
        subject=subject,
        body=message,
        attachment=attachment,
        attachment_name=attachment_name or "",
        attachment_type=attachment_type,
        descrizione=descrizione[:120],
        modello=modello,
        oggetto_id=oggetto_id,
    )


def invia_voce_coda(voce):
    """Spedisce una voce di coda e aggiorna stato e documento collegato.

    Rilancia l'eccezione se l'invio fallisce (il chiamante decide se riprovare).
    """
    from .models import EmailInCoda

    email = EmailMessage(
        subject=voce.subject,
        body=voce.body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[voce.to_email],
    )
    if voce.attachment is not None:
        email.attach(voce.attachment_name or "allegato", bytes(voce.attachment), voce.attachment_type)
    try:
        email.send(fail_silently=False)
    except Exception as exc:
        voce.tentativi += 1
        voce.ultimo_errore = str(exc)[:300]
        if voce.tentativi >= TENTATIVI_MASSIMI:
            voce.stato = EmailInCoda.STATO_FALLITA
        voce.save(update_fields=["tentativi", "ultimo_errore", "stato"])
        raise
    voce.stato = EmailInCoda.STATO_INVIATA
    voce.sent_at = timezone.now()
    voce.ultimo_errore = ""
    voce.save(update_fields=["stato", "sent_at", "ultimo_errore"])
    _aggiorna_documento(voce)
    return True


def _aggiorna_documento(voce):
    """Dopo un invio riuscito, segna il documento come inviato (come prima)."""
    from .models import EmailInCoda

    if not voce.oggetto_id:
        return
    try:
        if voce.modello == EmailInCoda.MODELLO_PREVENTIVO:
            from apps.sales.models import Quote

            preventivo = Quote.objects.filter(pk=voce.oggetto_id, status=Quote.STATUS_DRAFT).first()
            if preventivo is not None:
                preventivo.status = Quote.STATUS_SENT
                preventivo.save(update_fields=["status", "updated_at"])
        elif voce.modello == EmailInCoda.MODELLO_FATTURA:
            from apps.billing import services as billing_services
            from apps.billing.models import SalesInvoice

            fattura = SalesInvoice.objects.filter(pk=voce.oggetto_id, status=SalesInvoice.STATUS_ISSUED).first()
            if fattura is not None:
                billing_services.mark_sales_invoice_sent(fattura)
        elif voce.modello == EmailInCoda.MODELLO_FATTURA_SDI:
            from apps.billing.models import SalesInvoice

            fattura = SalesInvoice.objects.filter(pk=voce.oggetto_id).first()
            if fattura is not None and fattura.sdi_status != SalesInvoice.SDI_SENT:
                fattura.sdi_status = SalesInvoice.SDI_SENT
                fattura.sdi_sent_at = timezone.now()
                fattura.sdi_note = ""
                fattura.save(update_fields=["sdi_status", "sdi_sent_at", "sdi_note", "updated_at"])
    except Exception:
        # Lo stato dell'email resta «inviata»: il documento si può segnare a mano.
        pass
