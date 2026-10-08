"""MCP del gestionale (trasporto stdio, sola lettura).

Espone i dati del gestionale agli assistenti AI in linguaggio naturale, senza
scritture: tutti gli attrezzi leggono soltanto il database. Le letture Django
( sincrone) girano in un thread dedicato via ``sync_to_async``. Avvio locale::

    .\\.venv\\Scripts\\python.exe scripts\\mcp_server.py

Per collegarlo a un client MCP (es. Claude Desktop, opencode) puntare il
comando sopra come server stdio.
"""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.db.models import Q  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("gestionale")


# ------------------------------------------------------------------ aiuti
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


# ------------------------------------------------------------------ clienti
def _cerca_clienti(testo, limite):
    from apps.contacts.models import Contact

    testo = (testo or "").strip()
    if len(testo) < 2:
        return [{"errore": "Scrivi almeno 2 caratteri."}]
    contatti = (
        Contact.objects.filter(
            Q(name__icontains=testo)
            | Q(code__icontains=testo)
            | Q(city__icontains=testo)
            | Q(email__icontains=testo)
            | Q(vat_number__icontains=testo)
        )
        .order_by("name")[: _limite(limite)]
    )
    return [
        {
            **_riga(c, "code", "name", "city", "email", "phone", "vat_number"),
            "cliente": c.is_customer,
            "fornitore": c.is_supplier,
        }
        for c in contatti
    ]


@mcp.tool()
async def cerca_clienti(testo: str, limite: int = 10) -> list:
    """Cerca clienti e fornitori per nome, codice, città, email o P.IVA."""
    return await sync_to_async(_cerca_clienti, thread_sensitive=True)(testo, limite)


def _scheda_cliente(codice):
    from django.utils import timezone

    from apps.billing.models import SalesInvoice
    from apps.contacts.models import Contact
    from apps.sales.models import Quote, SalesOrder

    contatto = Contact.objects.filter(code=(codice or "").strip()).first()
    if contatto is None:
        return {"errore": f"Nessun contatto con codice {codice!r}."}
    oggi = timezone.localdate()

    def _doc(r):
        return {
            "numero": r["number"],
            "data": _valore(r["date"]),
            "stato": r["status"],
            "imponibile": _valore(r["subtotal"]),
            "totale": _valore(r["grand_total"]),
        }

    preventivi = list(
        Quote.objects.filter(customer=contatto, status__in=[Quote.STATUS_DRAFT, Quote.STATUS_SENT])
        .order_by("-date")
        .values("number", "date", "status", "subtotal", "grand_total")[:10]
    )
    ordini = list(
        SalesOrder.objects.filter(
            customer=contatto, status__in=[SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CONFIRMED]
        )
        .order_by("-date")
        .values("number", "date", "status", "subtotal", "grand_total")[:10]
    )
    fatture = list(
        SalesInvoice.objects.filter(
            customer=contatto, status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT]
        ).order_by("due_date")[:20]
    )
    return {
        **_riga(
            contatto, "code", "name", "address", "zip_code", "city", "province",
            "email", "phone", "vat_number", "tax_code",
        ),
        "preventivi_aperti": [_doc(r) for r in preventivi],
        "ordini_aperti": [_doc(r) for r in ordini],
        "fatture_aperte": [
            {
                **_riga(f, "number", "date", "due_date", "status", "subtotal", "grand_total"),
                "scaduta": bool(f.due_date and f.due_date < oggi),
            }
            for f in fatture
        ],
    }


@mcp.tool()
async def scheda_cliente(codice: str) -> dict:
    """Scheda anagrafica di un cliente (per codice) con documenti aperti e fatture da incassare."""
    return await sync_to_async(_scheda_cliente, thread_sensitive=True)(codice)


# ---------------------------------------------------------------- preventivi
def _lista_preventivi(stato, cliente, limite):
    from apps.sales.models import Quote

    righe = Quote.objects.select_related("customer").order_by("-date", "-pk")
    stato = (stato or "").strip().lower()
    if stato:
        codici = {codice: etichetta for codice, etichetta in Quote.STATUS_CHOICES}
        trovato = next(
            (codice for codice, etichetta in codici.items()
             if stato in (codice.lower(), etichetta.lower())),
            None,
        )
        if trovato is None:
            return [{"errore": f"Stato {stato!r} non valido. Usa: {', '.join(codici)}."}]
        righe = righe.filter(status=trovato)
    if (cliente or "").strip():
        righe = righe.filter(customer__name__icontains=cliente.strip())
    return [
        {
            "numero": q.number,
            "data": _valore(q.date),
            "cliente": q.customer.name,
            "stato": q.get_status_display(),
            "imponibile": _valore(q.subtotal),
            "totale": _valore(q.grand_total),
        }
        for q in righe[: _limite(limite)]
    ]


@mcp.tool()
async def lista_preventivi(stato: str = "", cliente: str = "", limite: int = 20) -> list:
    """Elenca preventivi, più recenti prima. Stato: bozza, inviato, accettato, rifiutato, convertito (o vuoto)."""
    return await sync_to_async(_lista_preventivi, thread_sensitive=True)(stato, cliente, limite)


def _dettaglio_preventivo(numero):
    from apps.sales.models import Quote

    preventivo = (
        Quote.objects.select_related("customer", "payment_term")
        .filter(number=(numero or "").strip())
        .first()
    )
    if preventivo is None:
        return {"errore": f"Nessun preventivo con numero {numero!r}."}
    righe = []
    for riga in preventivo.lines.select_related("product", "uom", "vat_rate").order_by("position", "pk"):
        righe.append(
            {
                "tipo": riga.get_line_type_display(),
                "descrizione": riga.description or (str(riga.product) if riga.product_id else ""),
                "quantita": _valore(riga.qty),
                "um": riga.uom.code if riga.uom_id else "",
                "prezzo": _valore(riga.unit_price),
                "sconto_pct": _valore(riga.discount_pct),
                "iva": str(riga.vat_rate.rate) if riga.vat_rate_id else "",
                "importo": _valore(riga.line_subtotal),
            }
        )
    return {
        "numero": preventivo.number,
        "data": _valore(preventivo.date),
        "valido_fino_al": _valore(preventivo.valid_until),
        "stato": preventivo.get_status_display(),
        "cliente": preventivo.customer.name,
        "pagamento": preventivo.payment_term.name if preventivo.payment_term_id else "",
        "riferimento": preventivo.reference or "",
        "righe": righe,
        "imponibile": _valore(preventivo.subtotal),
        "totale_iva": _valore(preventivo.vat_total),
        "totale": _valore(preventivo.grand_total),
    }


@mcp.tool()
async def dettaglio_preventivo(numero: str) -> dict:
    """Dettaglio di un preventivo per numero: testata, righe e totali."""
    return await sync_to_async(_dettaglio_preventivo, thread_sensitive=True)(numero)


# ---------------------------------------------------------------- articoli
def _cerca_articoli(testo, limite):
    from apps.catalog.models import Product
    from apps.catalog.search import filtro_articoli

    testo = (testo or "").strip()
    if len(testo) < 2:
        return [{"errore": "Scrivi almeno 2 caratteri."}]
    articoli = Product.objects.filter(filtro_articoli(testo)).select_related("uom").order_by("name")[: _limite(limite)]
    return [
        {
            "codice": a.code,
            "nome": a.name,
            "um": a.uom.code if a.uom_id else "",
            "prezzo_vendita": _valore(a.sale_price),
            "giacenza_totale": _valore(a.total_stock),
        }
        for a in articoli
    ]


@mcp.tool()
async def cerca_articoli(testo: str, limite: int = 10) -> list:
    """Cerca articoli per nome, codice o codice a barre: prezzi e giacenza totale."""
    return await sync_to_async(_cerca_articoli, thread_sensitive=True)(testo, limite)


def _giacenza_articolo(codice):
    from apps.catalog.models import Product
    from apps.inventory.models import StockLevel

    articolo = Product.objects.filter(code=(codice or "").strip()).first()
    if articolo is None:
        return {"errore": f"Nessun articolo con codice {codice!r}."}
    livelli = StockLevel.objects.filter(product=articolo).select_related("warehouse").order_by("warehouse__name")
    return {
        "codice": articolo.code,
        "nome": articolo.name,
        "magazzini": [
            {"magazzino": str(livello.warehouse), "quantita": _valore(livello.quantity)} for livello in livelli
        ],
        "giacenza_totale": _valore(articolo.total_stock),
    }


@mcp.tool()
async def giacenza_articolo(codice: str) -> dict:
    """Giacenza di un articolo per magazzino e totale (per codice esatto)."""
    return await sync_to_async(_giacenza_articolo, thread_sensitive=True)(codice)


# ------------------------------------------------------------------ fatture
def _fatture_da_incassare(solo_scadute, limite):
    from django.utils import timezone

    from apps.billing.models import SalesInvoice

    oggi = timezone.localdate()
    fatture = SalesInvoice.objects.filter(
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT]
    ).select_related("customer")
    if solo_scadute:
        fatture = fatture.filter(due_date__lt=oggi)
    fatture = fatture.order_by("due_date")[: _limite(limite)]
    return [
        {
            **_riga(f, "number", "date", "due_date", "subtotal", "grand_total"),
            "cliente": f.customer.name,
            "stato": f.get_status_display(),
            "scaduta": bool(f.due_date and f.due_date < oggi),
        }
        for f in fatture
    ]


@mcp.tool()
async def fatture_da_incassare(solo_scadute: bool = False, limite: int = 20) -> list:
    """Fatture emesse non pagate (inviate o emesse), con flag scadute."""
    return await sync_to_async(_fatture_da_incassare, thread_sensitive=True)(solo_scadute, limite)


if __name__ == "__main__":
    mcp.run()
