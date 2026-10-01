"""Arrotondamenti del gestionale, in un unico posto.

Tutti gli importi e le quantità passano da qui, così il modo di arrotondare è
lo stesso ovunque: prima esisteva in tre file diversi e due di questi usavano
l'arrotondamento «bancario» di Python (ROUND_HALF_EVEN), che in fatturazione
non ci si aspetta — 0,665 diventava 0,66 invece di 0,67.

Qui si usa sempre l'arrotondamento commerciale: il mezzo va per eccesso.
"""
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
FOUR_PLACES = Decimal("0.0001")


def round2(value):
    """Arrotondamento commerciale a due decimali (importi in euro)."""
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round3(value):
    """Arrotondamento commerciale a tre decimali (quantità)."""
    return Decimal(value or 0).quantize(THREE_PLACES, rounding=ROUND_HALF_UP)


def round4(value):
    """Arrotondamento commerciale a quattro decimali (prezzi unitari)."""
    return Decimal(value or 0).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
