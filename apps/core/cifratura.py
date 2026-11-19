"""Cifratura delle password delle caselle email salvate nel database.

Le password SMTP (casella aziendale e caselle personali dei dipendenti) devono
essere rilette per spedire, quindi non si possono salvare come hash: si
cifrano con Fernet (AES + firma). La chiave deriva da ``SECRET_KEY``; le chiavi
in ``SECRET_KEY_FALLBACKS`` servono a rileggere le password dopo un cambio di
chiave. Se la chiave cambia senza fallback le password vanno reinserite.

Un backup del database da solo non basta per leggerle: serve anche la chiave,
che sta nel file .env del server.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

PREFISSO = "gestionale-password-email:"


def _chiave(segreto):
    impronta = hashlib.sha256((PREFISSO + str(segreto)).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(impronta)


def _fernet():
    segreti = [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
    return MultiFernet([Fernet(_chiave(segreto)) for segreto in segreti if segreto])


def cifra(testo):
    """Testo cifrato (stringa vuota resta vuota)."""
    if not testo:
        return ""
    return _fernet().encrypt(testo.encode("utf-8")).decode("ascii")


def decifra(testo):
    """Testo in chiaro, o stringa vuota se manca o non è leggibile."""
    if not testo:
        return ""
    try:
        return _fernet().decrypt(testo.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return ""
