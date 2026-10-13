"""Condiviso del server MCP del gestionale: istanza FastMCP e utilità.

Gli strumenti vivono in ``mcp_read.py`` (sola lettura) e ``mcp_write.py``
(scritture, che riusano i servizi dell'applicazione) e si registrano
sull'istanza ``mcp`` di questo modulo. Nessun import di Django a livello di
modulo: i modelli si importano dentro le singole funzioni, così lo setup di
Django resta centralizzato in ``mcp_server.py``.

Ogni strumento dichiara l'annotazione MCP più adatta (``LETTURA``,
``CREAZIONE``, ``MODIFICA`` o ``MODIFICA_RIPETIBILE``) e descrive i parametri
con ``Annotated`` e ``Field``: sono le informazioni che finiscono nello schema
dei tool che vedono gli assistenti.
"""
import functools
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

mcp = FastMCP("gestionale")

# --------------------------------------------------------------- annotazioni
# Hint MCP per i client: readOnlyHint, destructiveHint, idempotentHint,
# openWorldHint. Il server è locale e parla solo col database del gestionale:
# openWorldHint è sempre False e non ci sono mai cancellazioni.
LETTURA = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
CREAZIONE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
MODIFICA = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
MODIFICA_RIPETIBILE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)

# ---------------------------------------------------------- parametri comuni
Limite50 = Annotated[int, Field(ge=1, le=50, description="Numero massimo di righe restituite (1-50).")]
Limite200 = Annotated[int, Field(ge=1, le=200, description="Numero massimo di righe restituite (1-200).")]
DataDa = Annotated[str, Field(description="Data iniziale (AAAA-MM-GG o GG/MM/AAAA); vuota per nessun limite.")]
DataA = Annotated[str, Field(description="Data finale (AAAA-MM-GG o GG/MM/AAAA); vuota per nessun limite.")]
Offset = Annotated[int, Field(ge=0, description="Righe da saltare per la paginazione (0 = dall'inizio); la risposta riporta totale, has_more e prossimo_offset.")]


def _strumento(fn=None, *, annotazioni=None):
    """Registra una funzione sincrona come tool MCP.

    ``functools.wraps`` preserva la firma tipizzata della funzione originale:
    è da lì che FastMCP costruisce lo schema dei parametri che vedono gli
    assistenti. Gli errori previsti (validazioni, campi mancanti) tornano come
    dict ``{"errore": ...}`` invece di far fallire la chiamata. Uso:
    ``@_strumento(annotazioni=LETTURA)`` oppure ``@_strumento`` senza
    annotazioni.
    """

    def registra(fn):
        @functools.wraps(fn)
        async def esegui(*args, **kwargs):
            return await sync_to_async(_sicuro, thread_sensitive=True)(fn, *args, **kwargs)

        return mcp.tool(annotations=annotazioni)(esegui)

    if fn is None:
        return registra
    return registra(fn)


# ---------------------------------------------------------------- conversioni
def _valore(value):
    if isinstance(value, Decimal):
        # format "f" evita la notazione esponenziale di str() su Decimal
        return format(value, "f")
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


def _offset(n):
    """Numero di righe da saltare (mai negativo)."""
    try:
        return max(0, int(n))
    except (TypeError, ValueError):
        return 0


def _metadati(restituiti, totale, offset, limite):
    """Metadati di paginazione di un elenco (usati anche dai report a bucket)."""
    successivo = offset + restituiti if offset + restituiti < totale else None
    return {
        "totale": totale,
        "offset": offset,
        "limite": limite,
        "has_more": successivo is not None,
        "prossimo_offset": successivo,
    }


def _pagina(elenco, totale, offset, limite):
    """Risposta di un elenco: metadati di paginazione più i risultati."""
    return {**_metadati(len(elenco), totale, offset, limite), "risultati": elenco}


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
