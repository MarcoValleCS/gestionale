"""Funzioni di utilità condivise."""
from decimal import Decimal, InvalidOperation


def to_decimal(value, default=Decimal("0")):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def format_quantity(value):
    """Formatta una quantità senza zeri inutili (12.500 -> 12,5)."""
    if value is None:
        return ""
    value = to_decimal(value)
    text = f"{value:f}".rstrip("0").rstrip(".")
    if text == "-0":
        text = "0"
    return text.replace(".", ",")


def format_money(value):
    """Formatta un importo in stile italiano (1234.5 -> 1.234,50)."""
    if value is None:
        return ""
    value = to_decimal(value).quantize(Decimal("0.01"))
    text = f"{value:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")
