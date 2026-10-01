"""Ruoli applicativi e relative protezioni per viste e funzioni."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

ROLE_ADMIN = "Amministratore"
ROLE_SALES = "Vendite"
ROLE_PURCHASING = "Acquisti"
ROLE_WAREHOUSE = "Magazzino"
ROLE_HR = "Personale"

ALL_ROLES = [ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_WAREHOUSE, ROLE_HR]

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Accesso completo a tutte le funzioni, impostazioni e utenti.",
    ROLE_SALES: "Contatti, articoli, preventivi e ordini cliente.",
    ROLE_PURCHASING: "Contatti, articoli, ordini fornitore e listini.",
    ROLE_WAREHOUSE: "Giacenze, movimenti di magazzino, ricezione merci e consegne.",
    ROLE_HR: "Dipendenti, registrazione ore, ferie e permessi.",
}


def has_role(user, *roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


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
