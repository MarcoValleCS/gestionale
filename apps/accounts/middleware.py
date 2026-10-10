"""Limitazione dell'accesso per i collaboratori esterni.

Un collaboratore (scavo, elettricista, piastrellista…) entra nel gestionale solo
per rendicontare le proprie ore. Se il suo utente ha *soltanto* il ruolo
«Collaboratore», ogni altra pagina gli viene preclusa e viene riportato alla sua
area: così non vede prezzi, margini, clienti o documenti.

Chi ha anche un altro ruolo (o è amministratore) non viene limitato: un
dipendente dell'ufficio che collabora anche ai cantieri mantiene l'accesso pieno.
"""
from django.shortcuts import redirect

from .permissions import COLLABORATOR_AREA_PREFIX, RESTRICTED_ROLES, ROLE_COLLABORATOR

# Pagine sempre raggiungibili: accesso, uscita, cambio password, file statici
ALWAYS_ALLOWED_PREFIXES = ("/accounts/", "/static/", "/media/", "/guida/")
ALWAYS_ALLOWED_EXACT = ("/manifest.webmanifest", "/sw.js", "/offline/")


def is_collaborator_only(user, ruoli=None):
    """True se l'utente ha il ruolo «Collaboratore» e nessun altro.

    Si possono passare i gruppi già letti (``ruoli``) per evitare una seconda
    query quando il chiamante li ha già caricati.
    """
    if not user or not user.is_authenticated or user.is_superuser:
        return False
    ruoli = set(user.groups.values_list("name", flat=True)) if ruoli is None else set(ruoli)
    if ROLE_COLLABORATOR not in ruoli:
        return False
    return not (ruoli - set(RESTRICTED_ROLES))


class CollaboratorRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # I gruppi servono anche al context processor dei ruoli: si leggono una
        # sola volta qui e si riusano, così ogni pagina risparmia una query.
        utente = getattr(request, "user", None)
        if utente and utente.is_authenticated and not utente.is_superuser:
            request._ruoli_cache = set(utente.groups.values_list("name", flat=True))
        if is_collaborator_only(utente, ruoli=getattr(request, "_ruoli_cache", None)):
            percorso = request.path
            consentito = (
                percorso.startswith(ALWAYS_ALLOWED_PREFIXES)
                or percorso.startswith(COLLABORATOR_AREA_PREFIX)
                or percorso in ALWAYS_ALLOWED_EXACT
            )
            if not consentito:
                return redirect("hr:collaborator_area")
        return self.get_response(request)
