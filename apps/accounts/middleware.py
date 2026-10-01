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
ALWAYS_ALLOWED_PREFIXES = ("/accounts/", "/static/", "/media/")
ALWAYS_ALLOWED_EXACT = ("/manifest.webmanifest", "/sw.js", "/offline/")


def is_collaborator_only(user):
    """True se l'utente ha il ruolo «Collaboratore» e nessun altro."""
    if not user or not user.is_authenticated or user.is_superuser:
        return False
    ruoli = set(user.groups.values_list("name", flat=True))
    if ROLE_COLLABORATOR not in ruoli:
        return False
    return not (ruoli - set(RESTRICTED_ROLES))


class CollaboratorRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_collaborator_only(getattr(request, "user", None)):
            percorso = request.path
            consentito = (
                percorso.startswith(ALWAYS_ALLOWED_PREFIXES)
                or percorso.startswith(COLLABORATOR_AREA_PREFIX)
                or percorso in ALWAYS_ALLOWED_EXACT
            )
            if not consentito:
                return redirect("hr:collaborator_area")
        return self.get_response(request)
