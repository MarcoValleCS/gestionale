"""Registro delle modifiche: chi ha creato, cambiato o cancellato cosa.

Con più persone che lavorano sullo stesso database, quando un dato non torna
serve poter risalire a chi l'ha toccato. Il registro si aggancia ai salvataggi
dei modelli principali (documenti, articoli, contatti) e annota l'utente che
stava usando il gestionale in quel momento.

L'utente arriva da un ``ContextVar`` impostato dal middleware: i segnali di
Django non ricevono la richiesta, quindi si passa da lì.
"""
import contextvars
import logging

from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

# Utente della richiesta in corso (vuoto per le operazioni da console o cron)
utente_corrente = contextvars.ContextVar("utente_corrente", default=None)

# Campi che non vale la pena confrontare: cambiano da soli
CAMPI_IGNORATI = {"updated_at", "created_at", "cached_stock"}

# Modelli sorvegliati: vengono registrati da ``sorveglia``
MODELLI_SORVEGLIATI = {}


def utente_attuale():
    utente = utente_corrente.get()
    if utente is not None and getattr(utente, "is_authenticated", False):
        return utente
    return None


def registrazione_attiva():
    return not _sospensione.get()


_sospensione = contextvars.ContextVar("registro_sospeso", default=False)


class RegistroAttivitaMiddleware:
    """Rende disponibile l'utente della richiesta ai segnali di salvataggio."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = utente_corrente.set(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            utente_corrente.reset(token)


def descrivi(istanza):
    """Etichetta leggibile dell'oggetto, per il registro."""
    numero = getattr(istanza, "number", None)
    codice = getattr(istanza, "code", None)
    nome = getattr(istanza, "name", None)
    if numero:
        return str(numero)[:120]
    if codice and nome:
        return f"{codice} – {nome}"[:120]
    if nome:
        return str(nome)[:120]
    if codice:
        return str(codice)[:120]
    return str(istanza)[:120]


def _istantanea(istanza):
    valori = {}
    for campo in istanza._meta.concrete_fields:
        if campo.name in CAMPI_IGNORATI:
            continue
        valori[campo.name] = getattr(istanza, campo.attname, None)
    return valori


def _campi_cambiati(prima, dopo):
    cambiati = []
    for nome, valore in prima.items():
        if dopo.get(nome) != valore:
            cambiati.append(nome)
    return cambiati


def registra(azione, istanza, dettagli=""):
    """Scrive una riga nel registro (mai un errore fatale)."""
    from .models import ActivityLog

    if not registrazione_attiva():
        return
    utente = utente_attuale()
    try:
        ActivityLog.objects.create(
            user=utente,
            action=azione,
            model_name=istanza._meta.verbose_name,
            object_id=str(getattr(istanza, "pk", "") or ""),
            object_label=descrivi(istanza),
            details=dettagli[:300],
        )
    except Exception:  # il registro non deve mai bloccare il salvataggio
        logger.exception("Impossibile scrivere nel registro attività")


def _prima_del_salvataggio(sender, instance, **kwargs):
    if sender not in MODELLI_SORVEGLIATI or not instance.pk:
        return
    try:
        precedente = sender.objects.filter(pk=instance.pk).first()
    except Exception:
        precedente = None
    instance._registro_prima = _istantanea(precedente) if precedente else None


def _dopo_il_salvataggio(sender, instance, created, **kwargs):
    if sender not in MODELLI_SORVEGLIATI:
        return
    if created:
        registra("creato", instance)
        return
    prima = getattr(instance, "_registro_prima", None)
    if prima is None:
        registra("modificato", instance)
        return
    cambiati = _campi_cambiati(prima, _istantanea(instance))
    if not cambiati:
        return
    etichette = ", ".join(cambiati[:6])
    if len(cambiati) > 6:
        etichette += f" e altri {len(cambiati) - 6}"
    registra("modificato", instance, etichette)


def _alla_cancellazione(sender, instance, **kwargs):
    if sender not in MODELLI_SORVEGLIATI:
        return
    registra("cancellato", instance)


def sorveglia(*modelli):
    """Registra i modelli da tenere sotto controllo nel registro."""
    for modello in modelli:
        MODELLI_SORVEGLIATI[modello] = modello._meta.verbose_name


post_save.connect(_dopo_il_salvataggio, dispatch_uid="registro_post_save")
post_delete.connect(_alla_cancellazione, dispatch_uid="registro_post_delete")


def connetti_pre_save():
    """Aggancia il pre_save una volta sola (dopo il caricamento delle app)."""
    from django.db.models.signals import pre_save

    pre_save.connect(_prima_del_salvataggio, dispatch_uid="registro_pre_save")


class registro_sospeso:
    """Sospende il registro mentre si fanno operazioni massive.

    Con ``with registro_sospeso():`` i salvataggi non finiscono nel registro:
    serve ai comandi che creano dati in blocco (dati dimostrativi, importazioni),
    dove il registro sarebbe solo rumore.
    """

    def __enter__(self):
        self.token = _sospensione.set(True)
        return self

    def __exit__(self, *exc):
        _sospensione.reset(self.token)
        return False


_sospensione = contextvars.ContextVar("registro_sospeso", default=False)
