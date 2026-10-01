"""Filtri template personalizzati."""
from django import template
from django.utils.safestring import mark_safe

from ..richtext import clean_notes
from ..utils import format_money, format_quantity

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
def multiply(value, arg):
    try:
        return value * arg
    except Exception:
        return ""
