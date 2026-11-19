"""Connessione IMAP alle caselle email (aziendale o personale).

Il gestionale non legge più la posta in arrivo: IMAP serve solo a copiare
nella cartella «Inviati» le email spedite dal gestionale, così si ritrovano
anche in Outlook o nella webmail di chi le ha mandate.
"""
import imaplib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class PostaNonConfigurata(Exception):
    """Mancano server o credenziali IMAP."""


def credenziali_aziendali():
    """Server, utente e password IMAP della casella aziendale.

    Se in Impostazioni › Email è indicata una casella di invio con la sua
    password si usa quella (server IMAP ricavato da quello SMTP), altrimenti
    le variabili ``IMAP_*`` del file .env.
    """
    from .mailing import configurazione_smtp, host_imap_per

    configurazione = configurazione_smtp()
    if configurazione["da_impostazioni"] and configurazione["password"]:
        return host_imap_per(configurazione["host"]), configurazione["utente"], configurazione["password"]
    return (
        getattr(settings, "IMAP_HOST", ""),
        getattr(settings, "IMAP_USER", ""),
        getattr(settings, "IMAP_PASSWORD", ""),
    )


def posta_configurata():
    """True se si può aprire la casella aziendale via IMAP."""
    return all(credenziali_aziendali())


def connetti(utente=None, password=None, host=None):
    """Apre la connessione IMAP (SSL) alla casella aziendale o a quella indicata."""
    if utente is None:
        host, utente, password = credenziali_aziendali()
    host = host or getattr(settings, "IMAP_HOST", "")
    if not (host and utente and password):
        raise PostaNonConfigurata("Manca la configurazione IMAP della casella.")
    client = imaplib.IMAP4_SSL(host, getattr(settings, "IMAP_PORT", 993), timeout=30)
    client.login(utente, password)
    return client
