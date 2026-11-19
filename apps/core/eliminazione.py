"""Eliminazione sicura delle anagrafiche: solo se non c'è niente di collegato.

Un cantiere creato per sbaglio, un contatto doppio o un articolo mai usato si
possono cancellare; se invece qualcosa li usa (preventivi, ordini, fatture,
ore, foto, movimenti di magazzino…) l'eliminazione si blocca e si dice cosa
c'è di collegato. Così nessun documento perde il suo cliente o il suo
cantiere senza che nessuno se ne accorga.

I collegamenti si leggono dai modelli (tutte le chiavi esterne che puntano
all'oggetto, anche quelle nascoste): una relazione aggiunta in futuro blocca
l'eliminazione da sola, senza dover aggiornare un elenco a mano.
"""
from django.db import models, transaction
from django.db.models.deletion import ProtectedError, RestrictedError


def collegamenti(oggetto, propri=()):
    """Cosa è collegato all'oggetto: elenco di (descrizione, quantità).

    ``propri`` sono i nomi delle relazioni che fanno parte dell'oggetto stesso
    e se ne vanno con lui (es. i componenti di un kit): non bloccano.
    """
    risultato = []
    for relazione in oggetto._meta.get_fields(include_hidden=True):
        if not (relazione.auto_created and not relazione.concrete):
            continue
        if not (relazione.one_to_many or relazione.one_to_one or relazione.many_to_many):
            continue
        modello = relazione.related_model
        if modello._meta.auto_created:
            # tabelle intermedie delle relazioni molti-a-molti (es. etichette)
            continue
        nome = relazione.get_accessor_name() or relazione.name
        if nome in propri or relazione.name in propri:
            continue
        campo = relazione.field
        if campo.many_to_many:
            numero = modello._default_manager.filter(**{campo.name: oggetto}).count()
        elif isinstance(campo, models.ForeignKey):
            numero = modello._default_manager.filter(**{campo.name: oggetto.pk}).count()
        else:
            continue
        if numero:
            descrizione = modello._meta.verbose_name if numero == 1 else modello._meta.verbose_name_plural
            risultato.append((str(descrizione), numero))
    return risultato


def descrivi_collegamenti(elenco):
    """«2 preventivi, 1 ordine fornitore» (per i messaggi all'utente)."""
    return ", ".join(f"{numero} {descrizione.lower()}" for descrizione, numero in elenco)


def elimina_se_libero(oggetto, propri=()):
    """Elimina l'oggetto se nulla lo usa. Restituisce l'elenco dei collegamenti
    che bloccano (vuoto = eliminato).

    Il controllo e la cancellazione stanno nella stessa transazione; se nel
    frattempo qualcuno ha collegato un documento con una relazione protetta,
    il database rifiuta e si risponde come se il collegamento ci fosse già.
    """
    with transaction.atomic():
        bloccanti = collegamenti(oggetto, propri=propri)
        if bloccanti:
            return bloccanti
        try:
            oggetto.delete()
        except (ProtectedError, RestrictedError):
            return collegamenti(oggetto, propri=propri) or [("documenti collegati", 1)]
    return []
