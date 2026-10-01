"""Protezione dalle modifiche contemporanee sugli stessi dati.

Con più utenti collegati capita che due persone aprano lo stesso documento e lo
salvino entrambe: senza controllo l'ultimo salvataggio sovrascrive in silenzio
il lavoro dell'altro. ``ConflictAwareUpdateView`` confronta la data di ultima
modifica vista all'apertura della pagina con quella presente nel database al
momento del salvataggio e, se è cambiata, rifiuta il salvataggio avvisando.

Il controllo è agganciato a ``dispatch`` e non a ``post`` perché molte viste di
documento (preventivi, ordini, fatture) ridefiniscono ``post`` per gestire le
righe: un metodo definito nella classe avrebbe la precedenza sul mixin e il
controllo non verrebbe mai eseguito. ``dispatch`` è invece sempre invocato.

Non serve modificare i template: il riferimento viene tenuto nella sessione
dell'utente, che è già per-utente.
"""
from django.contrib import messages
from django.core.exceptions import FieldError
from django.db import models
from django.shortcuts import redirect

SESSION_PREFIX = "concurrency_seen"

# Esiti che indicano che il salvataggio è andato a buon fine
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def seen_key(model, pk):
    return f"{SESSION_PREFIX}:{model._meta.label_lower}:{pk}"


class ConflictAwareUpdateView:
    """Mixin per ``UpdateView``: rileva se un altro utente ha salvato nel frattempo.

    Va elencato **prima** delle altre classi::

        class QuoteUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
            ...
    """

    conflict_message = (
        "Un altro utente ha salvato delle modifiche a questo elemento mentre lo stavi "
        "compilando. Per non sovrascrivere il suo lavoro la tua modifica non è stata "
        "salvata: la pagina è stata ricaricata con i dati aggiornati, controllali e riprova."
    )

    # ------------------------------------------------------------- strumenti
    def _target(self, kwargs):
        """(modello, pk) dell'oggetto in modifica, oppure (None, None)."""
        model = getattr(self, "model", None)
        if model is None or not (isinstance(model, type) and issubclass(model, models.Model)):
            return None, None
        pk = kwargs.get(getattr(self, "pk_url_kwarg", None) or "pk")
        if not pk:
            return None, None
        return model, pk

    def _current_stamp(self, model, pk):
        """Data di ultima modifica presente ora nel database (None se assente)."""
        try:
            return model.objects.filter(pk=pk).values_list("updated_at", flat=True).first()
        except FieldError:
            return None

    def _remember(self, request, kwargs):
        model, pk = self._target(kwargs)
        if model is None:
            return
        current = self._current_stamp(model, pk)
        if current is not None:
            request.session[seen_key(model, pk)] = current.isoformat()

    def _has_conflict(self, request, kwargs):
        model, pk = self._target(kwargs)
        if model is None:
            return False
        stored = request.session.get(seen_key(model, pk))
        if not stored:
            # L'utente non ha mai aperto la pagina: non c'è nulla da proteggere.
            return False
        current = self._current_stamp(model, pk)
        if current is None:
            return False
        return current.isoformat() != stored

    # -------------------------------------------------------------- agganci
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        self._remember(request, kwargs)
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and self._has_conflict(request, kwargs):
            messages.error(request, self.conflict_message)
            # Ricarica la pagina in lettura: il modulo viene ripresentato con i
            # dati aggiornati, senza salvare nulla.
            return redirect(request.get_full_path())

        response = super().dispatch(request, *args, **kwargs)

        if request.method == "POST" and getattr(response, "status_code", None) in REDIRECT_STATUSES:
            # Salvataggio riuscito: allinea il riferimento, così un secondo invio
            # dalla stessa pagina non viene scambiato per un conflitto.
            self._remember(request, kwargs)
        return response
