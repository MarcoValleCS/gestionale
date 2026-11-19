"""Invio email dei documenti (fatture, preventivi) con PDF in allegato.

L'invio vero avviene in background (vedi ``EmailInCoda``): la pagina accoda
e risponde subito, così un server SMTP lento non blocca il gestionale.

Da quale casella parte un'email
-------------------------------
- **Casella personale**: se l'utente che spedisce ha email e password della
  propria casella (es. simone@aquaforma.it), l'email parte da lì e le risposte
  tornano a lui. Aruba rifiuta un From diverso dall'account con cui ci si
  autentica («Mittente non consentito»): per questo serve la sua password.
- **Casella aziendale** (email di invio predefinita): per chi non ha una
  casella personale, per lo SDI e per gli avvisi automatici. Si configura in
  Impostazioni › Email; se lì è vuota valgono le variabili ``EMAIL_*`` del
  file .env. L'email dell'utente, se c'è, finisce in Reply-To.
"""
import logging
import smtplib
from dataclasses import dataclass
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone

logger = logging.getLogger(__name__)

TENTATIVI_MASSIMI = 3

# Server usato quando non è indicato né nelle impostazioni né nel file .env
SERVER_PREDEFINITO = "smtps.aruba.it"
BACKEND_SMTP = "django.core.mail.backends.smtp.EmailBackend"


# ------------------------------------------------------------ configurazione
def _porta_per(sicurezza):
    from .models import CompanySettings

    return {CompanySettings.SICUREZZA_SSL: 465, CompanySettings.SICUREZZA_TLS: 587}.get(sicurezza, 25)


def host_imap_per(host_smtp):
    """Server IMAP della stessa casella: smtps.aruba.it → imaps.aruba.it.

    Serve per la copia in Inviati. Se il nome non segue lo schema smtp./smtps.
    si usa ``IMAP_HOST`` del file .env.
    """
    host = (host_smtp or "").strip().lower()
    for prefisso, imap in (("smtps.", "imaps."), ("smtp.", "imap.")):
        if host.startswith(prefisso):
            return imap + host[len(prefisso):]
    return getattr(settings, "IMAP_HOST", "")


def server_smtp(azienda=None):
    """Server, porta e protezione della casella aziendale."""
    from .models import CompanySettings

    azienda = azienda or CompanySettings.load()
    if azienda.smtp_host:
        host = azienda.smtp_host
        sicurezza = azienda.smtp_sicurezza or CompanySettings.SICUREZZA_SSL
        porta = azienda.smtp_porta
    elif settings.EMAIL_HOST:
        host = settings.EMAIL_HOST
        if azienda.smtp_sicurezza:
            sicurezza = azienda.smtp_sicurezza
        elif settings.EMAIL_USE_SSL:
            sicurezza = CompanySettings.SICUREZZA_SSL
        elif settings.EMAIL_USE_TLS:
            sicurezza = CompanySettings.SICUREZZA_TLS
        else:
            sicurezza = CompanySettings.SICUREZZA_NESSUNA
        porta = azienda.smtp_porta or settings.EMAIL_PORT
    else:
        host = SERVER_PREDEFINITO
        sicurezza = azienda.smtp_sicurezza or CompanySettings.SICUREZZA_SSL
        porta = azienda.smtp_porta
    if not porta:
        porta = _porta_per(sicurezza)
    return {"host": host, "porta": porta, "sicurezza": sicurezza}


def server_caselle_personali(azienda=None):
    """Server delle caselle dei dipendenti (es. simone@aquaforma.it).

    È separato da quello aziendale perché quest'ultimo può essere la PEC
    (per lo SDI), che non accetta le credenziali delle caselle normali.
    """
    from .models import CompanySettings

    azienda = azienda or CompanySettings.load()
    host = (azienda.caselle_host or SERVER_PREDEFINITO).strip()
    sicurezza = azienda.caselle_sicurezza or CompanySettings.SICUREZZA_SSL
    porta = _porta_per(sicurezza)
    if ":" in host:
        nome, numero = host.rsplit(":", 1)
        if numero.isdigit():
            host, porta = nome, int(numero)
    return {"host": host, "porta": porta, "sicurezza": sicurezza}


def configurazione_smtp():
    """Casella aziendale effettiva: server, credenziali e mittente.

    ``da_impostazioni`` è True quando la casella è quella indicata in
    Impostazioni › Email (e non quella del file .env).
    """
    from .models import CompanySettings

    azienda = CompanySettings.load()
    server = server_smtp(azienda)
    nome = (azienda.mittente_nome or azienda.name or "").strip()
    if azienda.mittente_email:
        utente = (azienda.smtp_utente or azienda.mittente_email).strip()
        password = azienda.password_smtp
        if not password and utente.lower() == (settings.EMAIL_HOST_USER or "").strip().lower():
            # stessa casella del file .env: non serve riscriverne la password
            password = settings.EMAIL_HOST_PASSWORD
        indirizzo = azienda.mittente_email
        configurata = bool(utente and password)
        da_impostazioni = True
    else:
        utente = settings.EMAIL_HOST_USER
        password = settings.EMAIL_HOST_PASSWORD
        _nome_env, indirizzo = parseaddr(settings.DEFAULT_FROM_EMAIL)
        configurata = bool(getattr(settings, "EMAIL_IS_CONFIGURED", False))
        da_impostazioni = False
    if da_impostazioni or azienda.mittente_nome:
        mittente = formataddr((nome, indirizzo)) if nome else indirizzo
    else:
        mittente = settings.DEFAULT_FROM_EMAIL
    return {
        **server,
        "utente": utente,
        "password": password,
        "indirizzo": indirizzo,
        "mittente": mittente,
        "configurata": configurata,
        "da_impostazioni": da_impostazioni,
    }


def email_configured(utente=None):
    """True se si può spedire: casella aziendale pronta o casella personale dell'utente."""
    if utente is not None and getattr(utente, "ha_casella_personale", False):
        return True
    return configurazione_smtp()["configurata"]


@dataclass
class Mittente:
    """Da dove parte un'email: indirizzo, Reply-To e credenziali della casella."""

    from_email: str
    reply_to: str
    utente: str
    password: str
    personale: bool
    host: str
    porta: int
    sicurezza: str
    da_impostazioni: bool
    host_imap: str = ""  # solo per le caselle personali (copia in Inviati)

    @property
    def intestazioni(self):
        return {"Reply-To": self.reply_to} if self.reply_to else {}


def mittente_aziendale(reply_to=""):
    configurazione = configurazione_smtp()
    risposta = (reply_to or "").strip()
    if risposta.lower() == (configurazione["indirizzo"] or "").lower():
        risposta = ""
    return Mittente(
        from_email=configurazione["mittente"],
        reply_to=risposta,
        utente=configurazione["utente"],
        password=configurazione["password"],
        personale=False,
        host=configurazione["host"],
        porta=configurazione["porta"],
        sicurezza=configurazione["sicurezza"],
        da_impostazioni=configurazione["da_impostazioni"],
    )


def mittente_per(utente=None, from_email=""):
    """Casella da usare per l'utente: la sua se configurata, altrimenti quella aziendale."""
    if utente is not None and getattr(utente, "ha_casella_personale", False):
        server = server_caselle_personali()
        nome = (utente.get_full_name() or "").strip()
        return Mittente(
            from_email=formataddr((nome, utente.email)) if nome else utente.email,
            reply_to="",
            utente=utente.email.strip(),
            password=utente.password_casella,
            personale=True,
            host=server["host"],
            porta=server["porta"],
            sicurezza=server["sicurezza"],
            da_impostazioni=True,
            host_imap=host_imap_per(server["host"]),
        )
    risposta = from_email or (getattr(utente, "email", "") if utente is not None else "")
    return mittente_aziendale(reply_to=risposta)


def _backend(mittente):
    """Sistema di invio: quello delle impostazioni Django, ma SMTP vero per le
    caselle configurate dal gestionale anche quando il file .env non ha
    l'SMTP (lì Django scriverebbe solo nel log). Nei test resta locmem."""
    backend = settings.EMAIL_BACKEND
    if mittente.da_impostazioni and backend.endswith("console.EmailBackend"):
        return BACKEND_SMTP
    return backend


def _connessione(mittente):
    from .models import CompanySettings

    return get_connection(
        _backend(mittente),
        fail_silently=False,
        host=mittente.host,
        port=mittente.porta,
        username=mittente.utente,
        password=mittente.password,
        use_ssl=mittente.sicurezza == CompanySettings.SICUREZZA_SSL,
        use_tls=mittente.sicurezza == CompanySettings.SICUREZZA_TLS,
        timeout=getattr(settings, "EMAIL_TIMEOUT", 20),
    )


def _messaggio(mittente, *, to_email, subject, body, attachment=None, attachment_name="",
               attachment_type="application/pdf"):
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=mittente.from_email,
        to=[to_email],
        headers=mittente.intestazioni or None,
        connection=_connessione(mittente),
    )
    if attachment is not None and attachment_name:
        email.attach(attachment_name, bytes(attachment), attachment_type)
    return email


def _spedisci(email, mittente):
    """Spedisce e copia il messaggio nella cartella Inviati della casella usata."""
    email.send(fail_silently=False)
    if _backend(mittente) == BACKEND_SMTP:
        # Solo quando l'email è partita davvero (non nel log o nei test)
        casella = (mittente.utente, mittente.password, mittente.host_imap) if mittente.personale else None
        archivia_in_inviati(email.message().as_bytes(), casella=casella)


def invia_subito(*, to_email, subject, message, utente=None, attachment=None, attachment_name="",
                 attachment_type="application/pdf", solo_personale=False):
    """Spedisce subito (senza coda): prove di invio e avvisi automatici.

    Con ``solo_personale`` usa la casella dell'utente o fallisce: serve alla
    prova della casella personale, che non deve ripiegare su quella aziendale.
    """
    mittente = mittente_per(utente)
    if solo_personale and not mittente.personale:
        raise ValueError("Casella personale non configurata: indica email e password.")
    email = _messaggio(
        mittente, to_email=to_email, subject=subject, body=message,
        attachment=attachment, attachment_name=attachment_name, attachment_type=attachment_type,
    )
    _spedisci(email, mittente)
    return mittente


def send_document_email(*, to_email, subject, message, attachment=None, attachment_name="", from_email="", utente=None):
    """Invia subito un documento per email. Restituisce True se il PDF è stato allegato.

    Usata solo nei test e da vecchi richiami: le viste usano ``accoda_email``
    per non bloccare la pagina.
    """
    mittente = mittente_per(utente, from_email)
    email = _messaggio(
        mittente, to_email=to_email, subject=subject, body=message,
        attachment=attachment, attachment_name=attachment_name,
    )
    _spedisci(email, mittente)
    return bool(attachment)


# ------------------------------------------------------------------- coda
def accoda_email(*, to_email, subject, message, attachment=None, attachment_name="",
                 attachment_type="application/pdf", descrizione="", modello="libera", oggetto_id=None,
                 from_email="", utente=None):
    """Mette un'email in coda (un INSERT: millisecondi, niente rete).

    ``utente`` è chi spedisce: se ha una casella personale l'email parte da lì.
    """
    from .models import EmailInCoda

    if attachment_name and attachment is None:
        attachment_name = ""
    if utente is not None and not getattr(utente, "is_authenticated", False):
        utente = None
    if not from_email and utente is not None:
        from_email = utente.email or ""
    return EmailInCoda.objects.create(
        to_email=to_email,
        from_email=(from_email or "").strip(),
        inviata_da=utente,
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

    Se la casella personale rifiuta l'accesso (password cambiata), l'email
    parte comunque dalla casella aziendale e l'errore resta annotato sulla
    voce. Rilancia l'eccezione se l'invio fallisce (il chiamante decide se
    riprovare).
    """
    from .models import EmailInCoda

    mittente = mittente_per(voce.inviata_da, voce.from_email)
    nota = ""

    def prepara(chi):
        return _messaggio(
            chi, to_email=voce.to_email, subject=voce.subject, body=voce.body,
            attachment=voce.attachment, attachment_name=voce.attachment_name or ("allegato" if voce.attachment is not None else ""),
            attachment_type=voce.attachment_type,
        )

    try:
        try:
            _spedisci(prepara(mittente), mittente)
        except smtplib.SMTPAuthenticationError as exc:
            if not mittente.personale or not configurazione_smtp()["configurata"]:
                raise
            aziendale = mittente_aziendale(reply_to=mittente.utente)
            logger.warning("Casella %s: accesso rifiutato, invio dalla casella aziendale (%s)", mittente.utente, exc)
            nota = f"La casella {mittente.utente} ha rifiutato la password: inviata dalla casella aziendale."
            _spedisci(prepara(aziendale), aziendale)
    except Exception as exc:
        voce.tentativi += 1
        voce.ultimo_errore = str(exc)[:300]
        if voce.tentativi >= TENTATIVI_MASSIMI:
            voce.stato = EmailInCoda.STATO_FALLITA
        voce.save(update_fields=["tentativi", "ultimo_errore", "stato"])
        raise
    voce.stato = EmailInCoda.STATO_INVIATA
    voce.sent_at = timezone.now()
    voce.ultimo_errore = nota[:300]
    voce.save(update_fields=["stato", "sent_at", "ultimo_errore"])
    _aggiorna_documento(voce)
    return True


# --------------------------------------------------------- cartella Inviati
CARTELLE_INVIATI_CANDIDATE = ("Sent", "INBOX.Sent", "Posta inviata", "Sent Items", "Posta-inviata")


def _nome_cartella(testo):
    """Nome della cartella da una riga LIST di IMAP.

    Formato: ``(flag) "delimitatore" nome``. Il nome può essere quotato
    (``"Sent"``) oppure un atomo senza virgolette (``INBOX.Sent``: è così che
    Aruba espone le sue cartelle).
    """
    resto = testo.split(")", 1)[-1].strip()
    if not resto:
        return ""
    if resto.startswith('"'):
        chiusa = resto.find('"', 1)
        resto = resto[chiusa + 1:].strip()
    else:
        pezzi = resto.split(" ", 1)
        resto = pezzi[1].strip() if len(pezzi) > 1 else ""
    if not resto:
        return ""
    if resto.startswith('"') and resto.endswith('"') and len(resto) >= 2:
        return resto[1:-1]
    return resto


def _cartella_posta_inviata(client):
    """Nome della cartella Inviati: SPECIAL-USE \\Sent se esposto, altrimenti candidati noti."""
    try:
        stato, righe = client.list()
    except Exception:
        return ""
    if stato != "OK" or not righe:
        return ""
    nomi = []
    for riga in righe:
        testo = riga.decode("utf-8", "replace") if isinstance(riga, bytes) else str(riga)
        nome = _nome_cartella(testo)
        if not nome:
            continue
        if "\\Sent" in testo:
            return nome
        nomi.append(nome)
    for nome in nomi:
        if nome.lower() in {candidato.lower() for candidato in CARTELLE_INVIATI_CANDIDATE}:
            return nome
    return ""


def archivia_in_inviati(raw_message, casella=None):
    """Copia il messaggio appena inviato nella cartella Inviati via IMAP.

    ``casella`` è (utente, password, server IMAP) di una casella personale;
    senza, si usa la casella aziendale. Così la mail si ritrova anche in
    Outlook/webmail. Non solleva mai errori: se la copia fallisce, l'invio
    resta comunque valido.
    """
    from . import imap as posta_imap

    try:
        if casella is None:
            if not posta_imap.posta_configurata():
                return False
            client = posta_imap.connetti()
        else:
            client = posta_imap.connetti(*casella)
        try:
            cartella = _cartella_posta_inviata(client)
            if not cartella:
                return False
            import imaplib
            import time

            stato, _ = client.append(cartella, "\\Seen", imaplib.Time2Internaldate(time.time()), raw_message)
            return stato == "OK"
        finally:
            try:
                client.logout()
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Copia in Inviati non riuscita: %s", exc)
        return False


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
