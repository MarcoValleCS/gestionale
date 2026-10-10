"""Context processor per dati azienda e ruoli utente."""
from .models import CompanySettings

# Ruoli veri e propri: per l'amministratore sono tutti attivi
ROLE_FLAGS = ("is_admin", "is_sales", "is_purchasing", "is_warehouse", "is_hr", "is_collaborator")


def company(request):
    try:
        return {"company": CompanySettings.load()}
    except Exception:  # tabelle non ancora migrate
        return {"company": None}


def tema(request):
    """Colori e sfondo scelti dall'utente, pronti per il foglio di stile."""
    from django.templatetags.static import static

    symbol = static("brand/aquaforma-simbolo.png")
    lockup = static("brand/aquaforma-logo.png")
    try:
        azienda = CompanySettings.load()
    except Exception:  # tabelle non ancora migrate
        return {
            "tema": {
                "logo": "",
                "logo_menu": symbol,
                "logo_login": lockup,
                "logo_predefinito": symbol,
            }
        }
    laterale = azienda.sidebar_colors
    logo_personalizzato = azienda.app_logo_url
    return {
        "tema": {
            "colore": azienda.theme_color_hex,
            "colore_scuro": azienda.theme_color_dark,
            "colore_tenue": azienda.theme_color_soft,
            "sfondo": azienda.background_hex,
            "laterale_alto": laterale["top"],
            "laterale_centro": laterale["mid"],
            "laterale_basso": laterale["bottom"],
            "laterale_luce": laterale["glow"],
            "laterale_attivo": laterale["active"],
            "logo": logo_personalizzato,
            "logo_menu": logo_personalizzato or symbol,
            "logo_login": logo_personalizzato or lockup,
            "logo_predefinito": symbol,
            "stile_documenti": azienda.document_style,
        }
    }


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
        return {"roles": spento, "messaggi_non_letti": 0, "posta_non_lette": 0}

    if user.is_superuser:
        # l'amministratore ha tutti i ruoli e non è mai limitato
        return {
            "roles": {**{flag: True for flag in ROLE_FLAGS}, "is_collaborator_only": False},
            "messaggi_non_letti": _messaggi_non_letti(user),
            "posta_non_lette": _posta_non_letta(user),
        }

    names = getattr(request, "_ruoli_cache", None)
    if names is None:
        # Fuori dal middleware (es. nei test) si leggono qui una sola volta.
        names = set(user.groups.values_list("name", flat=True))
    else:
        names = set(names)
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
        },
        "messaggi_non_letti": _messaggi_non_letti(user),
        "posta_non_lette": _posta_non_letta(user),
    }


def _messaggi_non_letti(utente):
    """Quanti messaggi interni non letti ha l'utente (per il pallino nel menu)."""
    try:
        from .cache import memoizza
        from .models import InternalMessage

        def conta():
            return InternalMessage.objects.filter(recipient=utente, read_at__isnull=True).count()

        return memoizza(f"badge_msg_{utente.pk}", conta, 60)
    except Exception:  # tabelle non ancora migrate
        return 0


def _posta_non_letta(utente):
    """Quante email rilevanti non lette ci sono in casella."""
    try:
        from .cache import memoizza
        from .models import InboundEmail

        def conta():
            return InboundEmail.objects.filter(is_relevant=True, read_at__isnull=True).count()

        # Il conteggio è globale (non dipende dall'utente): una chiave sola.
        return memoizza("badge_posta", conta, 60)
    except Exception:
        return 0

