"""Context processor per dati azienda e ruoli utente."""
from .models import CompanySettings

# Ruoli veri e propri: per l'amministratore sono tutti attivi
ROLE_FLAGS = ("is_admin", "is_sales", "is_purchasing", "is_warehouse", "is_hr", "is_collaborator")


def company(request):
    try:
        return {"company": CompanySettings.load()}
    except Exception:  # tabelle non ancora migrate
        return {"company": None}


def roles(request):
    """Flag dei ruoli per i template.

    ``is_collaborator_only`` è a parte e non fa parte dei ruoli: indica che
    l'utente va limitato alla sola area ore. Deve restare False per
    l'amministratore, altrimenti gli si nasconde tutto il menu.
    """
    user = getattr(request, "user", None)
    spento = {flag: False for flag in ROLE_FLAGS}
    spento["is_collaborator_only"] = False

    if not user or not user.is_authenticated:
        return {"roles": spento}

    if user.is_superuser:
        # l'amministratore ha tutti i ruoli e non è mai limitato
        return {"roles": {**{flag: True for flag in ROLE_FLAGS}, "is_collaborator_only": False}}

    names = set(user.groups.values_list("name", flat=True))
    return {
        "roles": {
            "is_admin": "Amministratore" in names,
            "is_sales": "Vendite" in names,
            "is_purchasing": "Acquisti" in names,
            "is_warehouse": "Magazzino" in names,
            "is_hr": "Personale" in names,
            "is_collaborator": "Collaboratore" in names,
            # limitato solo se ha il ruolo Collaboratore e nessun altro
            "is_collaborator_only": "Collaboratore" in names and names <= {"Collaboratore"},
        }
    }
