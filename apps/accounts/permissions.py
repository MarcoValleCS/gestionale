"""Ruoli applicativi e relative protezioni per viste e funzioni."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

ROLE_ADMIN = "Amministratore"
ROLE_SALES = "Vendite"
ROLE_PURCHASING = "Acquisti"
ROLE_WAREHOUSE = "Magazzino"
ROLE_HR = "Personale"
ROLE_COLLABORATOR = "Collaboratore"

ALL_ROLES = [ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_WAREHOUSE, ROLE_HR, ROLE_COLLABORATOR]

# Ruolo particolare: chi ce l'ha da solo può accedere unicamente alla propria
# area di rendicontazione delle ore (vedi apps.accounts.middleware).
RESTRICTED_ROLES = [ROLE_COLLABORATOR]

# Prefisso delle pagine riservate ai collaboratori (apps.hr è incluso sotto /personale/)
COLLABORATOR_AREA_PREFIX = "/personale/mio-lavoro/"

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Accesso completo a tutte le funzioni, impostazioni e utenti.",
    ROLE_SALES: "Contatti, articoli, preventivi e ordini cliente.",
    ROLE_PURCHASING: "Contatti, articoli, ordini fornitore e listini.",
    ROLE_WAREHOUSE: "Giacenze, movimenti di magazzino, ricezione merci e consegne.",
    ROLE_HR: "Dipendenti, registrazione ore, ferie e permessi.",
    ROLE_COLLABORATOR: "Solo la propria area: registra le ore lavorate sui cantieri.",
}


def ruoli_di(user):
    """Nomi dei ruoli (gruppi) dell'utente, letti dal database una volta sola.

    Il risultato resta sull'oggetto utente: ``request.user`` viene ricaricato a
    ogni richiesta, quindi vale per la richiesta in corso. Senza questa memoria
    ogni ``has_role`` (menu, ricerca, guida…) era una query in più.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return frozenset()
    ruoli = getattr(user, "_ruoli_cache", None)
    if ruoli is None:
        ruoli = frozenset(user.groups.values_list("name", flat=True))
        try:
            user._ruoli_cache = ruoli
        except AttributeError:  # oggetti che non accettano attributi
            pass
    return frozenset(ruoli)


def has_role(user, *roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return not ruoli_di(user).isdisjoint(roles)


def role_required(*roles):
    """Decoratore per viste basate su funzione."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if has_role(request.user, *roles):
                return view(request, *args, **kwargs)
            raise PermissionDenied("Non hai i permessi necessari per questa operazione.")

        return wrapped

    return decorator


class RoleRequiredMixin:
    """Mixin per viste basate su classe: impostare ``allowed_roles``."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if has_role(request.user, *self.allowed_roles):
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied("Non hai i permessi necessari per questa operazione.")
