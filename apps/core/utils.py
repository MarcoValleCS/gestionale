"""Funzioni di utilità condivise."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


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
    if value.as_tuple().exponent < -4:
        # arrotondamento commerciale, coerente col resto del gestionale
        value = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    text = f"{value:f}".rstrip("0").rstrip(".")
    if text == "-0":
        text = "0"
    return text.replace(".", ",")


def format_money(value):
    """Formatta un importo in stile italiano (1234.5 -> 1.234,50)."""
    if value is None:
        return ""
    value = to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{value:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------- colori
def normalizza_colore(value, fallback="#2563eb"):
    """Restituisce un colore esadecimale valido (o il fallback)."""
    testo = (value or "").strip()
    if len(testo) == 7 and testo.startswith("#"):
        try:
            int(testo[1:], 16)
            return testo.lower()
        except ValueError:
            return fallback
    return fallback


def _componenti(colore):
    colore = normalizza_colore(colore)[1:]
    return tuple(int(colore[i:i + 2], 16) for i in (0, 2, 4))


def mescola_colori(colore_a, colore_b, quantita):
    """Mescola due colori: 0 = solo il primo, 1 = solo il secondo."""
    quantita = max(0.0, min(1.0, float(quantita)))
    a = _componenti(colore_a)
    b = _componenti(colore_b)
    misto = tuple(round(x + (y - x) * quantita) for x, y in zip(a, b))
    return "#%02x%02x%02x" % misto


def scurisci(colore, quantita=0.2):
    return mescola_colori(colore, "#000000", quantita)


def schiarisci(colore, quantita=0.85):
    return mescola_colori(colore, "#ffffff", quantita)


def rgba(colore, alpha=0.35):
    r, g, b = _componenti(colore)
    return f"rgba({r}, {g}, {b}, {alpha})"
