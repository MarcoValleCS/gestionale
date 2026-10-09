"""Condiviso del server MCP del gestionale: istanza FastMCP e utilità.

Gli strumenti vivono in ``mcp_read.py`` (sola lettura) e ``mcp_write.py``
(scritture, che riusano i servizi dell'applicazione) e si registrano
sull'istanza ``mcp`` di questo modulo. Nessun import di Django a livello di
modulo: i modelli si importano dentro le singole funzioni, così lo setup di
Django resta centralizzato in ``mcp_server.py``.
"""
import functools
from datetime import date, datetime
from decimal import Decimal

from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gestionale")


def _strumento(fn):
    """Registra una funzione sincrona come tool MCP.

    ``functools.wraps`` preserva la firma tipizzata della funzione originale:
    è da lì che FastMCP costruisce lo schema dei parametri che vedono gli
    assistenti. Gli errori previsti (validazioni, campi mancanti) tornano come
    dict ``{"errore": ...}`` invece di far fallire la chiamata.
    """

    @functools.wraps(fn)
    async def esegui(*args, **kwargs):
        return await sync_to_async(_sicuro, thread_sensitive=True)(fn, *args, **kwargs)

    return mcp.tool()(esegui)


# ---------------------------------------------------------------- conversioni
def _valore(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value if value is not None else ""


def _riga(obj, *campi):
    return {nome: _valore(getattr(obj, nome, "")) for nome in campi}


def _limite(n, massimo=50):
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 10
    return max(1, min(n, massimo))


def _dec(valore, default=0):
    """Converte un valore (numero o stringa) in Decimal; vuoto/non valido → default."""
    if valore is None:
        return Decimal(str(default))
    if isinstance(valore, str):
        valore = valore.strip().replace(",", ".")
        if not valore:
            return Decimal(str(default))
    try:
        return Decimal(str(valore))
    except Exception:
        raise ValueError(f"Valore numerico non valido: {valore!r}.")


# ---------------------------------------------------------------------- date
def _data(testo, campo="data"):
    """Converte una data (AAAA-MM-GG o GG/MM/AAAA) in ``date``; None se vuota."""
    testo = (testo or "").strip()
    if not testo:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data {campo} non valida ({testo!r}): usa AAAA-MM-GG o GG/MM/AAAA.")


def _intervallo(da_testo="", a_testo=""):
    """Intervallo di date opzionale (entrambe le estremità possono mancare)."""
    da = _data(da_testo, "da_data")
    a = _data(a_testo, "a_data")
    if da and a and da > a:
        raise ValueError("da_data non può essere successiva ad a_data.")
    return da, a


def _stato_codice(testo, scelte, campo="stato"):
    """Converte uno stato in codice: accetta codice o etichetta italiana.

    Restituisce ``None`` se il testo è vuoto; alza ``ValueError`` se lo stato
    non è fra quelli ammessi (con l'elenco dei valori validi).
    """
    testo = (testo or "").strip().lower()
    if not testo:
        return None
    for codice, etichetta in scelte:
        if testo in (codice.lower(), etichetta.lower()):
            return codice
    ammessi = ", ".join(f"{codice} ({etichetta})" for codice, etichetta in scelte)
    raise ValueError(f"{campo.capitalize()} {testo!r} non valido. Valori ammessi: {ammessi}.")


# -------------------------------------------------------------------- errori
def _messaggio_errore(exc):
    messaggi = getattr(exc, "messages", None)
    if messaggi:
        return " ".join(str(m) for m in messaggi)
    return str(exc)


def _sicuro(fn, *args, **kwargs):
    """Esegue uno strumento intercettando gli errori previsti in un dict."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - uno strumento non deve mai esplodere
        from django.core.exceptions import ObjectDoesNotExist, ValidationError

        if isinstance(exc, (ValidationError, ValueError, TypeError, LookupError, ObjectDoesNotExist)):
            return {"errore": _messaggio_errore(exc)}
        raise


# --------------------------------------------------------------- documenti
def _righe_documento(doc):
    """Righe di un documento, con quantità consegnate/ricevute dove presenti."""
    righe = []
    for riga in doc.lines.select_related("product", "uom", "vat_rate").order_by("position", "pk"):
        voce = {
            "posizione": riga.position,
            "tipo": riga.get_line_type_display(),
            "descrizione": riga.label,
            "quantita": _valore(riga.qty),
            "um": riga.uom.code if riga.uom_id else "",
            "prezzo": _valore(riga.unit_price),
            "sconto_pct": _valore(riga.discount_pct),
            "iva": str(riga.vat_rate.rate) if riga.vat_rate_id else "",
            "importo": _valore(riga.line_subtotal),
        }
        if hasattr(riga, "qty_delivered"):
            voce["quantita_consegnata"] = _valore(riga.qty_delivered)
            voce["quantita_residua"] = _valore(riga.qty_remaining)
        if hasattr(riga, "qty_received"):
            voce["quantita_ricevuta"] = _valore(riga.qty_received)
            voce["quantita_residua"] = _valore(riga.qty_remaining)
        righe.append(voce)
    return righe


def _totali(doc):
    return {
        "imponibile": _valore(doc.subtotal),
        "totale_iva": _valore(doc.vat_total),
        "totale": _valore(doc.grand_total),
    }
