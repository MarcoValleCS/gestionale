"""Filtri template personalizzati."""
import re
from decimal import Decimal

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from ..richtext import clean_notes
from ..utils import format_money, format_quantity, to_decimal

register = template.Library()

BADGE_CLASSES = {
    # Preventivi
    "draft": "secondary",
    "sent": "info",
    "accepted": "success",
    "rejected": "danger",
    "converted": "primary",
    # Ordini
    "confirmed": "info",
    "partially": "warning",
    "delivered": "success",
    "received": "success",
    "received_partial": "warning",
    "cancelled": "dark",
    # Cantieri
    "survey": "info",
    "quote": "secondary",
    "in_progress": "warning",
    "testing": "info",
    "closed": "success",
    # Fatturazione
    "issued": "primary",
    "paid": "success",
    "registered": "warning",
    "new": "info",
    "ok": "success",
    "error": "danger",
    # Fatturazione elettronica
    "generated": "info",
    "delivered": "success",
    "accepted": "success",
    "rejected": "danger",
    "failed": "danger",
    "not_sent": "secondary",
    # Ferie e permessi
    "requested": "warning",
    "approved": "success",
}


@register.filter
def money(value):
    return format_money(value)


@register.filter
def qty(value):
    return format_quantity(value)


@register.filter
def badge_class(status):
    return BADGE_CLASSES.get(status, "secondary")


@register.filter
def richtext(value):
    """Rende le note formattate in sicurezza.

    Ripulisce l'HTML con una lista bianca e lo segna come sicuro: il filtro è
    l'unico punto in cui le note vengono rese come HTML, così ciò che arriva
    dall'editor, dall'admin o da vecchi dati passa sempre dallo stesso controllo.
    """
    return mark_safe(clean_notes(value))


@register.filter
def guida(value):
    """Rende il contenuto di una pagina della guida (titoli, elenchi, link)."""
    from ..richtext import clean_guida

    return mark_safe(clean_guida(value))


_URL_RE = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}/[^\s<>\"']+)",
    re.IGNORECASE,
)
_NON_TESTO_RE = re.compile(r"(<a\b[^>]*>.*?</a>|<[^>]+>)", re.IGNORECASE | re.DOTALL)
_PUNTEGGIATURA_FINALE = ".,;:!?)"


def _sostituisci_url(match):
    url = match.group(0)
    coda = ""
    while url and url[-1] in _PUNTEGGIATURA_FINALE:
        coda = url[-1] + coda
        url = url[:-1]
    href = url if re.match(r"https?://", url, re.IGNORECASE) else "https://" + url
    return f'<a href="{escape(href)}">{escape(url)}</a>' + coda


@register.filter
def linkify_urls(value):
    """Rende cliccabili gli URL scritti in chiaro (scheda, stampa e PDF).

    Opera su HTML già sanificato (es. dopo ``richtext``): collega solo gli
    URL fuori dai tag e dai link esistenti. Così anche i documenti creati
    prima del link cliccabile mostrano «aquaforma.space/termini» cliccabile.
    """
    if not value:
        return ""
    parti = _NON_TESTO_RE.split(str(value))
    for i in range(0, len(parti), 2):
        parti[i] = _URL_RE.sub(_sostituisci_url, parti[i])
    return mark_safe("".join(parti))


@register.filter
def net_price(value):
    """Prezzo unitario per i documenti che vanno al cliente.

    Lo sconto di riga non compare in stampa: il prezzo mostrato è quindi già
    quello effettivo. Si usano due decimali quando bastano, quattro quando
    servono davvero (prezzi bassi con sconto), così il cliente può rifare il
    conto senza trovare differenze di un centesimo.
    """
    importo = to_decimal(value)
    if importo == importo.quantize(Decimal("0.01")):
        return format_money(importo)
    testo = f"{importo.quantize(Decimal('0.0001')):,.4f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def multiply(value, arg):
    try:
        return value * arg
    except Exception:
        return ""
