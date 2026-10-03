"""Lettura della casella email aziendale via IMAP.

Il gestionale si collega alla casella (Aruba, o qualunque provider IMAP) e copia
le email nel database: la posta si legge dal gestionale senza aprire un client
di posta, e resta consultabile anche se la casella non risponde.

Il corpo e gli allegati si scaricano alla prima apertura del messaggio: la
sincronizzazione scarica solo le intestazioni, così è veloce anche con molta
posta.
"""
import email
import imaplib
import logging
from datetime import timezone as dt_timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class PostaNonConfigurata(Exception):
    """Manca la configurazione IMAP nel file .env."""


def posta_configurata():
    return bool(getattr(settings, "IMAP_IS_CONFIGURED", False))


def connetti():
    """Apre la connessione IMAP (SSL)."""
    if not posta_configurata():
        raise PostaNonConfigurata("Manca la configurazione IMAP: compila le variabili IMAP_* nel file .env.")
    client = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT, timeout=30)
    client.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
    return client


def _testo(valore):
    """Decodifica un'intestazione (gestisce accenti e codifiche strane)."""
    if not valore:
        return ""
    try:
        return str(make_header(decode_header(valore)))
    except Exception:
        return str(valore)


def _data(valore):
    if not valore:
        return None
    try:
        quando = parsedate_to_datetime(valore)
    except Exception:
        return None
    if quando is None:
        return None
    if timezone.is_naive(quando):
        quando = quando.replace(tzinfo=dt_timezone.utc)
    return quando


def _indirizzo(valore):
    """Estrae (nome, email) da un'intestazione From."""
    if not valore:
        return "", ""
    try:
        from email.utils import parseaddr

        nome, indirizzo = parseaddr(valore)
        return _testo(nome), indirizzo.strip()
    except Exception:
        return "", str(valore).strip()


def sincronizza(limite=100, cartella=None):
    """Copia le ultime email dalla casella al database.

    Restituisce un riepilogo: quante esaminate, quante nuove, eventuali errori.
    """
    from .models import InboundEmail

    cartella = cartella or settings.IMAP_FOLDER
    esito = {"esaminate": 0, "nuove": 0, "errori": []}

    client = connetti()
    try:
        stato, dati = client.select(cartella, readonly=True)
        if stato != "OK":
            raise PostaNonConfigurata(f"Cartella «{cartella}» non disponibile: {dati}")

        stato, dati = client.search(None, "ALL")
        if stato != "OK":
            raise PostaNonConfigurata(f"Ricerca non riuscita: {dati}")

        uid_esistenti = set(InboundEmail.objects.filter(folder=cartella).values_list("uid", flat=True))
        numeri = dati[0].split()
        numeri = numeri[-limite:]  # le più recenti
        esito["esaminate"] = len(numeri)

        for numero in numeri:
            stato, risposta = client.fetch(numero, "(RFC822.HEADER)")
            if stato != "OK" or not risposta or not isinstance(risposta[0], tuple):
                continue
            messaggio = email.message_from_bytes(risposta[0][1])
            uid = f"{cartella}:{numero.decode()}"
            if uid in uid_esistenti:
                continue
            nome, indirizzo = _indirizzo(messaggio.get("From"))
            InboundEmail.objects.create(
                uid=uid,
                folder=cartella,
                message_id=_testo(messaggio.get("Message-ID"))[:255],
                sender_name=nome[:200],
                sender_email=indirizzo[:254],
                recipients=_testo(messaggio.get("To"))[:500],
                subject=_testo(messaggio.get("Subject"))[:300] or "(senza oggetto)",
                received_at=_data(messaggio.get("Date")),
            )
            esito["nuove"] += 1
    finally:
        try:
            client.logout()
        except Exception:
            pass

    _collega_contatti()
    return esito


def _collega_contatti():
    """Aggancia le email ricevute ai contatti in anagrafica, quando possibile."""
    from apps.contacts.models import Contact

    from .models import InboundEmail

    indirizzi = {}
    for contatto in Contact.objects.exclude(email="").only("pk", "email"):
        indirizzi.setdefault(contatto.email.strip().lower(), contatto.pk)

    da_collegare = InboundEmail.objects.filter(contact__isnull=True).exclude(sender_email="")
    for messaggio in da_collegare:
        contatto_id = indirizzi.get(messaggio.sender_email.strip().lower())
        if contatto_id:
            messaggio.contact_id = contatto_id
            messaggio.save(update_fields=["contact", "updated_at"])


def _corpo(messaggio):
    """Estrae testo e HTML dal messaggio, con l'elenco degli allegati."""
    testo = ""
    html = ""
    allegati = []
    indice = 0
    for parte in messaggio.walk():
        tipo = parte.get_content_type()
        disposizione = str(parte.get("Content-Disposition") or "")
        nome_file = parte.get_filename()
        if nome_file:
            nome_file = _testo(nome_file)
        if "attachment" in disposizione.lower() or (nome_file and tipo not in ("text/plain", "text/html")):
            contenuto = parte.get_payload(decode=True) or b""
            allegati.append(
                {
                    "indice": indice,
                    "nome": (nome_file or f"allegato-{indice + 1}")[:150],
                    "tipo": tipo,
                    "dimensione": len(contenuto),
                }
            )
            indice += 1
            continue
        if tipo == "text/plain" and not testo:
            testo = (parte.get_payload(decode=True) or b"").decode(parte.get_content_charset() or "utf-8", "replace")
        elif tipo == "text/html" and not html:
            html = (parte.get_payload(decode=True) or b"").decode(parte.get_content_charset() or "utf-8", "replace")
    return testo, html, allegati


def scarica_corpo(messaggio_db):
    """Scarica dalla casella il corpo del messaggio e lo salva."""
    client = connetti()
    try:
        client.select(messaggio_db.folder, readonly=True)
        numero = messaggio_db.uid.split(":")[-1]
        stato, risposta = client.fetch(numero, "(RFC822)")
        if stato != "OK" or not risposta or not isinstance(risposta[0], tuple):
            raise PostaNonConfigurata("Il messaggio non è più presente nella casella.")
        messaggio = email.message_from_bytes(risposta[0][1])
        testo, html, allegati = _corpo(messaggio)
    finally:
        try:
            client.logout()
        except Exception:
            pass

    messaggio_db.body_text = testo
    messaggio_db.body_html = html
    messaggio_db.attachments = allegati
    messaggio_db.body_loaded = True
    messaggio_db.save(update_fields=["body_text", "body_html", "attachments", "body_loaded", "updated_at"])
    return messaggio_db


def scarica_allegato(messaggio_db, indice):
    """Restituisce (nome, tipo, contenuto) dell'allegato richiesto."""
    client = connetti()
    try:
        client.select(messaggio_db.folder, readonly=True)
        numero = messaggio_db.uid.split(":")[-1]
        stato, risposta = client.fetch(numero, "(RFC822)")
        if stato != "OK" or not risposta or not isinstance(risposta[0], tuple):
            raise PostaNonConfigurata("Il messaggio non è più presente nella casella.")
        messaggio = email.message_from_bytes(risposta[0][1])
        _, _, allegati = _corpo(messaggio)
    finally:
        try:
            client.logout()
        except Exception:
            pass

    for parte in messaggio.walk():
        nome = parte.get_filename()
        if not nome:
            continue
        voci = [a for a in allegati if a["nome"] == _testo(nome)]
        if not voci:
            continue
        if voci[0]["indice"] != int(indice):
            continue
        contenuto = parte.get_payload(decode=True) or b""
        return _testo(nome), parte.get_content_type(), contenuto
    raise PostaNonConfigurata("Allegato non trovato.")
