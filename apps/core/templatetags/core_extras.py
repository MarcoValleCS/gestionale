"""Filtri template personalizzati."""
from django import template

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
def multiply(value, arg):
    try:
        return value * arg
    except Exception:
        return ""
