"""Context processor per dati azienda e ruoli utente."""
from .models import CompanySettings


def company(request):
    try:
        return {"company": CompanySettings.load()}
    except Exception:  # tabelle non ancora migrate
        return {"company": None}


def roles(request):
    user = getattr(request, "user", None)
    empty = {
        "is_admin": False,
        "is_sales": False,
        "is_purchasing": False,
        "is_warehouse": False,
        "is_hr": False,
        "is_collaborator": False,
        "is_collaborator_only": False,
    }
    if not user or not user.is_authenticated:
        return {"roles": empty}
    if user.is_superuser:
        return {"roles": {k: True for k in empty}}
    names = set(user.groups.values_list("name", flat=True))
    solo_collaboratore = "Collaboratore" in names and names <= {"Collaboratore"}
    return {
        "roles": {
            "is_admin": "Amministratore" in names,
            "is_sales": "Vendite" in names,
            "is_purchasing": "Acquisti" in names,
            "is_warehouse": "Magazzino" in names,
            "is_hr": "Personale" in names,
            "is_collaborator": "Collaboratore" in names,
            "is_collaborator_only": solo_collaboratore,
        }
    }
