"""Strumenti MCP del gestionale per le scritture.

Creano e aggiornano i documenti riusando la logica di business già presente in
``apps/*/services.py`` (conversioni, conferme, consegne, fatturazioni,
movimenti di magazzino): gli strumenti non reimplementano regole, si limitano
a tradurre la richiesta in linguaggio naturale nelle chiamate ai servizi. Ogni
scrittura è esplicita: non ci sono cancellazioni, quelle restano nell'interfaccia
del gestionale.
"""
from typing import Optional

from mcp_common import _data, _dec, _stato_codice, _strumento, _valore


# ============================================================== risoluzioni
def _risolvi_contatto(testo):
    """Contatto per codice esatto o, se univoco, per parte del nome."""
    from apps.contacts.models import Contact

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare un contatto (codice o nome).")
    contatto = Contact.objects.filter(code__iexact=testo).first()
    if contatto is not None:
        return contatto
    trovati = list(Contact.objects.filter(name__icontains=testo)[:5])
    if not trovati:
        raise ValueError(f"Nessun contatto che contiene {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(f"{c.code} {c.name}" for c in trovati)
        raise ValueError(f"Più contatti trovati per {testo!r}: {elenco}. Usa il codice.")
    return trovati[0]


def _risolvi_prodotto(testo):
    """Articolo per codice esatto o, se univoco, per parte del nome."""
    from apps.catalog.models import Product

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare un articolo (codice o nome).")
    prodotto = Product.objects.filter(code__iexact=testo).first()
    if prodotto is not None:
        return prodotto
    trovati = list(Product.objects.filter(name__icontains=testo)[:5])
    if not trovati:
        raise ValueError(f"Nessun articolo che contiene {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(f"{p.code} {p.name}" for p in trovati)
        raise ValueError(f"Più articoli trovati per {testo!r}: {elenco}. Usa il codice.")
    return trovati[0]


def _risolvi_uom(codice):
    from apps.core.models import UnitOfMeasure

    codice = (codice or "").strip()
    if not codice:
        raise ValueError("Specificare l'unità di misura (es. pz, kg, m, h).")
    uom = UnitOfMeasure.objects.filter(code__iexact=codice).first()
    if uom is None:
        disponibili = ", ".join(UnitOfMeasure.objects.values_list("code", flat=True)[:20])
        raise ValueError(f"Unità di misura {codice!r} inesistente. Disponibili: {disponibili}.")
    return uom


def _risolvi_iva(testo, uso="vendita"):
    """Aliquota IVA per codice o percentuale; se vuota, quella predefinita."""
    from decimal import Decimal, InvalidOperation

    from apps.core.models import VatRate

    testo = (testo or "").strip()
    if not testo:
        predefinita = VatRate.default_for_sales() if uso == "vendita" else VatRate.default_for_purchase()
        if predefinita is None:
            raise ValueError("Nessuna aliquota IVA predefinita configurata: specificare il codice IVA.")
        return predefinita
    iva = VatRate.objects.filter(code__iexact=testo).first()
    if iva is not None:
        return iva
    try:
        iva = VatRate.objects.filter(rate=Decimal(testo.replace(",", "."))).first()
    except InvalidOperation:
        iva = None
    if iva is None:
        disponibili = ", ".join(f"{v.code} ({v.rate}%)" for v in VatRate.objects.all()[:20])
        raise ValueError(f"Aliquota IVA {testo!r} inesistente. Disponibili: {disponibili}.")
    return iva


def _risolvi_pagamento(testo):
    from apps.core.models import PaymentTerm

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare una condizione di pagamento.")
    pagamento = PaymentTerm.objects.filter(name__iexact=testo).first()
    if pagamento is None:
        trovati = list(PaymentTerm.objects.filter(name__icontains=testo)[:5])
        if len(trovati) == 1:
            return trovati[0]
        disponibili = ", ".join(PaymentTerm.objects.values_list("name", flat=True)[:20])
        raise ValueError(f"Condizione di pagamento {testo!r} inesistente. Disponibili: {disponibili}.")
    return pagamento


def _risolvi_cantiere(testo):
    from apps.jobs.models import Job

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare un cantiere.")
    cantiere = Job.objects.filter(code__iexact=testo).first()
    if cantiere is not None:
        return cantiere
    trovati = list(Job.objects.filter(name__icontains=testo)[:5])
    if not trovati:
        raise ValueError(f"Nessun cantiere che contiene {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(f"{j.code} {j.name}" for j in trovati)
        raise ValueError(f"Più cantieri trovati per {testo!r}: {elenco}. Usa il codice.")
    return trovati[0]


def _risolvi_magazzino(testo):
    """Magazzino per codice o nome; se vuoto, quello predefinito."""
    from django.db.models import Q

    from apps.inventory.models import Warehouse

    testo = (testo or "").strip()
    if not testo:
        magazzino = Warehouse.get_default()
        if magazzino is None:
            raise ValueError("Nessun magazzino configurato.")
        return magazzino
    magazzino = Warehouse.objects.filter(Q(code__iexact=testo) | Q(name__icontains=testo)).first()
    if magazzino is None:
        disponibili = ", ".join(f"{w.code} {w.name}" for w in Warehouse.objects.all()[:20])
        raise ValueError(f"Magazzino {testo!r} inesistente. Disponibili: {disponibili}.")
    return magazzino


def _risolvi_fase(testo):
    from apps.leads.models import LeadStage

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare la fase del lead.")
    fase = LeadStage.objects.filter(name__iexact=testo).first()
    if fase is None:
        trovati = list(LeadStage.objects.filter(name__icontains=testo)[:5])
        if len(trovati) == 1:
            return trovati[0]
        disponibili = ", ".join(LeadStage.objects.values_list("name", flat=True)[:20])
        raise ValueError(f"Fase {testo!r} inesistente. Disponibili: {disponibili}.")
    return fase


def _risolvi_lead(testo):
    from apps.leads.models import Lead

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare il lead (nome o parte del nome).")
    lead = Lead.objects.filter(name__iexact=testo).first()
    if lead is not None:
        return lead
    trovati = list(Lead.objects.filter(name__icontains=testo)[:5])
    if not trovati:
        raise ValueError(f"Nessun lead che contiene {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(l.name for l in trovati)
        raise ValueError(f"Più lead trovati per {testo!r}: {elenco}. Usa il nome esatto.")
    return trovati[0]


def _risolvi_utente(testo):
    from django.db.models import Q

    from apps.accounts.models import User

    testo = (testo or "").strip()
    if not testo:
        return None
    utente = User.objects.filter(username__iexact=testo).first()
    if utente is not None:
        return utente
    trovati = list(
        User.objects.filter(
            Q(username__icontains=testo) | Q(first_name__icontains=testo) | Q(last_name__icontains=testo)
        )[:5]
    )
    if len(trovati) == 1:
        return trovati[0]
    disponibili = ", ".join(User.objects.values_list("username", flat=True)[:20])
    raise ValueError(f"Utente {testo!r} inesistente. Disponibili: {disponibili}.")


def _risolvi_documento(modello, numero, etichetta):
    numero = (numero or "").strip()
    if not numero:
        raise ValueError(f"Specificare il numero dell'{etichetta}.")
    documento = modello.objects.filter(number=numero).first()
    if documento is None:
        raise ValueError(f"Nessun {etichetta} con numero {numero!r}.")
    return documento


# ================================================================== righe
TIPI_RIGA = {"articolo": "article", "sezione": "section", "sottosezione": "subsection", "nota": "note"}


def _normalizza_righe(righe):
    """Valida e normalizza le righe in ingresso (lista di dizionari).

    Ogni riga accetta: tipo (articolo, sezione, sottosezione, nota),
    descrizione, articolo (codice o nome), quantita, um, prezzo, sconto_pct, iva.
    """
    if not isinstance(righe, (list, tuple)) or not righe:
        raise ValueError("righe deve essere una lista non vuota di dizionari, uno per riga del documento.")
    normalizzate = []
    for numero, dati in enumerate(righe, start=1):
        if not isinstance(dati, dict):
            raise ValueError(f"La riga {numero} non è un dizionario.")
        tipo = str(dati.get("tipo", "articolo") or "articolo").strip().lower()
        if tipo not in TIPI_RIGA:
            raise ValueError(f"Riga {numero}: tipo {tipo!r} non valido. Usa: {', '.join(TIPI_RIGA)}.")
        articolo = str(dati.get("articolo") or dati.get("codice_articolo") or "").strip()
        descrizione = str(dati.get("descrizione") or "").strip()
        if TIPI_RIGA[tipo] == "article" and not (articolo or descrizione):
            raise ValueError(f"Riga {numero}: serve almeno l'articolo o la descrizione.")
        normalizzate.append(
            {
                "line_type": TIPI_RIGA[tipo],
                "articolo": articolo,
                "descrizione": descrizione,
                "quantita": _dec(dati.get("quantita", 1), default=1),
                "um": str(dati.get("um") or "").strip(),
                "prezzo": dati.get("prezzo"),
                "sconto_pct": _dec(dati.get("sconto_pct", 0)),
                "iva": str(dati.get("iva") or "").strip(),
            }
        )
    return normalizzate


def _crea_righe(cls_linea, campo, documento, righe_valide, uso="vendita"):
    """Scrive le righe di un documento (già validate da ``_normalizza_righe``)."""
    create = 0
    for posizione, dati in enumerate(righe_valide, start=1):
        prodotto = _risolvi_prodotto(dati["articolo"]) if dati["articolo"] else None
        prezzo = dati["prezzo"]
        if prezzo in (None, ""):
            if prodotto is not None:
                prezzo = prodotto.sale_price if uso == "vendita" else prodotto.purchase_price
            else:
                prezzo = 0
        if dati["um"]:
            um = _risolvi_uom(dati["um"])
        else:
            um = prodotto.uom if prodotto is not None else None
        if dati["iva"]:
            iva = _risolvi_iva(dati["iva"], uso)
        else:
            iva = (prodotto.sale_vat if uso == "vendita" else prodotto.purchase_vat) if prodotto is not None else None
        cls_linea.objects.create(
            **{campo: documento},
            position=posizione,
            line_type=dati["line_type"],
            product=prodotto,
            description=dati["descrizione"] or (prodotto.name if prodotto is not None else ""),
            qty=dati["quantita"],
            uom=um,
            unit_price=_dec(prezzo),
            discount_pct=dati["sconto_pct"],
            vat_rate=iva,
        )
        create += 1
    return create


def _riepilogo(doc):
    return {"numero": doc.number, "data": _valore(doc.date), "totale": _valore(doc.grand_total)}


# =============================================================== anagrafiche
@_strumento
def crea_cliente(
    ragione_sociale: str,
    tipo: str = "cliente",
    piva: str = "",
    cf: str = "",
    email: str = "",
    telefono: str = "",
    cellulare: str = "",
    indirizzo: str = "",
    cap: str = "",
    citta: str = "",
    provincia: str = "",
    pagamento: str = "",
    note: str = "",
) -> dict:
    """Crea un nuovo cliente o fornitore. tipo: cliente, fornitore o entrambi.
    pagamento è la condizione di pagamento (nome), opzionale."""
    from apps.contacts.models import Contact

    tipo = (tipo or "cliente").strip().lower()
    if tipo not in {"cliente", "fornitore", "entrambi"}:
        raise ValueError("tipo deve essere: cliente, fornitore o entrambi.")
    contatto = Contact(
        name=(ragione_sociale or "").strip(),
        is_customer=tipo in {"cliente", "entrambi"},
        is_supplier=tipo in {"fornitore", "entrambi"},
        vat_number=(piva or "").strip(),
        tax_code=(cf or "").strip(),
        email=(email or "").strip(),
        phone=(telefono or "").strip(),
        mobile=(cellulare or "").strip(),
        address=(indirizzo or "").strip(),
        zip_code=(cap or "").strip(),
        city=(citta or "").strip(),
        province=(provincia or "").strip(),
        notes=note or "",
    )
    if not contatto.name:
        raise ValueError("La ragione sociale è obbligatoria.")
    if pagamento:
        contatto.payment_term = _risolvi_pagamento(pagamento)
    contatto.full_clean()
    contatto.save()
    return {
        "messaggio": f"Contatto {contatto.code} creato.",
        "codice": contatto.code,
        "nome": contatto.name,
        "tipo": contatto.kind_label,
    }


@_strumento
def crea_articolo(
    nome: str,
    um: str,
    prezzo_vendita: float = 0,
    prezzo_acquisto: float = 0,
    categoria: str = "",
    iva_vendita: str = "",
    iva_acquisto: str = "",
    fornitore: str = "",
    barcode: str = "",
    scorta_minima: float = 0,
    gestito_a_magazzino: bool = True,
    note: str = "",
) -> dict:
    """Crea un articolo. um è il codice dell'unità di misura (es. pz, kg, m).
    Le aliquote IVA sono opzionali (altrimenti si usano quelle predefinite).
    La categoria viene creata se non esiste."""
    from apps.catalog.models import Category, Product

    prodotto = Product(
        name=(nome or "").strip(),
        uom=_risolvi_uom(um),
        sale_price=_dec(prezzo_vendita),
        purchase_price=_dec(prezzo_acquisto),
        sale_vat=_risolvi_iva(iva_vendita, "vendita"),
        purchase_vat=_risolvi_iva(iva_acquisto, "acquisto"),
        barcode=(barcode or "").strip(),
        min_stock=_dec(scorta_minima),
        is_stock_tracked=bool(gestito_a_magazzino),
        notes=note or "",
    )
    if not prodotto.name:
        raise ValueError("Il nome dell'articolo è obbligatorio.")
    if categoria:
        prodotto.category, _creata = Category.objects.get_or_create(name=categoria.strip())
    if fornitore:
        prodotto.main_supplier = _risolvi_contatto(fornitore)
    prodotto.full_clean()
    prodotto.save()
    return {
        "messaggio": f"Articolo {prodotto.code} creato.",
        "codice": prodotto.code,
        "nome": prodotto.name,
        "prezzo_vendita": _valore(prodotto.sale_price),
        "prezzo_acquisto": _valore(prodotto.purchase_price),
    }


@_strumento
def aggiorna_prezzo_articolo(
    codice: str, prezzo_vendita: Optional[float] = None, prezzo_acquisto: Optional[float] = None
) -> dict:
    """Aggiorna i prezzi di un articolo (vendita e/o acquisto). Specificare almeno un prezzo."""
    from apps.catalog.models import Product

    if prezzo_vendita is None and prezzo_acquisto is None:
        raise ValueError("Specificare almeno un prezzo da aggiornare.")
    prodotto = Product.objects.filter(code=(codice or "").strip()).first()
    if prodotto is None:
        raise ValueError(f"Nessun articolo con codice {codice!r}.")
    aggiornati = []
    if prezzo_vendita is not None:
        prodotto.sale_price = _dec(prezzo_vendita)
        aggiornati.append("sale_price")
    if prezzo_acquisto is not None:
        prodotto.purchase_price = _dec(prezzo_acquisto)
        aggiornati.append("purchase_price")
    prodotto.save(update_fields=aggiornati)
    return {
        "messaggio": f"Prezzi di {prodotto.code} aggiornati.",
        "codice": prodotto.code,
        "prezzo_vendita": _valore(prodotto.sale_price),
        "prezzo_acquisto": _valore(prodotto.purchase_price),
    }


# ================================================================= magazzino
@_strumento
def registra_movimento_magazzino(
    articolo: str,
    tipo: str,
    quantita: float,
    magazzino: str = "",
    prezzo: Optional[float] = None,
    riferimento: str = "",
    note: str = "",
) -> dict:
    """Registra un movimento di magazzino. tipo: carico, scarico o rettifica.
    Carico e scarico usano la quantità come valore assoluto (in entrata o uscita);
    la rettifica prende la quantità come differenza (positiva o negativa)."""
    from apps.inventory import services as inventory_services
    from apps.inventory.models import StockMovement

    codice_tipo = _stato_codice(tipo, StockMovement.TYPE_CHOICES, campo="tipo")
    if codice_tipo is None:
        raise ValueError("Specificare il tipo di movimento: carico, scarico o rettifica.")
    qta = _dec(quantita)
    if codice_tipo == StockMovement.TYPE_LOAD:
        delta = abs(qta)
    elif codice_tipo == StockMovement.TYPE_UNLOAD:
        delta = -abs(qta)
    else:
        delta = qta
    if delta == 0:
        raise ValueError("La quantità non può essere zero.")
    prodotto = _risolvi_prodotto(articolo)
    movimento = inventory_services.register_movement(
        product=prodotto,
        warehouse=_risolvi_magazzino(magazzino),
        delta=delta,
        movement_type=codice_tipo,
        note=(note or "").strip(),
        reference=(riferimento or "").strip(),
        unit_cost=_dec(prezzo) if prezzo is not None else None,
    )
    return {
        "messaggio": f"Movimento registrato per {prodotto.code}.",
        "articolo": prodotto.code,
        "tipo": movimento.get_movement_type_display(),
        "quantita": _valore(movimento.quantity),
        "giacenza_attuale": _valore(prodotto.total_stock),
    }


# ================================================================ preventivi
@_strumento
def crea_preventivo(
    cliente: str,
    righe: list,
    data: str = "",
    valido_fino_al: str = "",
    riferimento: str = "",
    note: str = "",
    condizioni: str = "",
    pagamento: str = "",
    cantiere: str = "",
    provvigione_a: str = "",
    provvigione_pct: float = 0,
) -> dict:
    """Crea un preventivo. righe è una lista di dizionari, uno per riga:
    {tipo: articolo|sezione|sottosezione|nota, descrizione, articolo, quantita, um, prezzo,
    sconto_pct, iva}. Per le righe articolo basta l'articolo (codice o nome) o la descrizione;
    prezzo, um e IVA si prenotano dall'articolo se non indicati."""
    from django.db import transaction
    from django.utils import timezone

    from apps.sales.models import Quote, QuoteLine

    righe_valide = _normalizza_righe(righe)
    with transaction.atomic():
        preventivo = Quote(
            customer=_risolvi_contatto(cliente),
            date=_data(data) or timezone.localdate(),
            valid_until=_data(valido_fino_al, "valido_fino_al"),
            reference=(riferimento or "").strip(),
            notes=note or "",
            terms_text=condizioni or "",
        )
        if pagamento:
            preventivo.payment_term = _risolvi_pagamento(pagamento)
        if cantiere:
            preventivo.job = _risolvi_cantiere(cantiere)
        if provvigione_a:
            preventivo.commission_contact = _risolvi_contatto(provvigione_a)
            preventivo.commission_pct = _dec(provvigione_pct)
        preventivo.save()
        numero_righe = _crea_righe(QuoteLine, "quote", preventivo, righe_valide, uso="vendita")
        preventivo.recalculate()
    return {"messaggio": f"Preventivo {preventivo.number} creato.", **_riepilogo(preventivo), "righe_create": numero_righe}


@_strumento
def cambia_stato_preventivo(numero: str, stato: str) -> dict:
    """Cambia lo stato di un preventivo: bozza, inviato, accettato o rifiutato.
    Per la conversione in ordine usare converti_preventivo_in_ordine."""
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    codice = _stato_codice(stato, Quote.STATUS_CHOICES, campo="stato")
    if codice is None:
        raise ValueError("Specificare il nuovo stato.")
    if preventivo.status == Quote.STATUS_CONVERTED:
        raise ValueError("Preventivo già convertito in ordine: lo stato non si modifica.")
    if codice == Quote.STATUS_CONVERTED:
        raise ValueError("Per convertire il preventivo usa converti_preventivo_in_ordine.")
    preventivo.status = codice
    preventivo.save(update_fields=["status"])
    return {"messaggio": f"Preventivo {preventivo.number}: stato «{preventivo.get_status_display()}».", **_riepilogo(preventivo)}


@_strumento
def duplica_preventivo(numero: str) -> dict:
    """Duplica un preventivo esistente in una nuova bozza, righe comprese."""
    from apps.sales import services as sales_services
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    copia = sales_services.duplicate_quote(preventivo)
    return {"messaggio": f"Preventivo {preventivo.number} duplicato.", **_riepilogo(copia)}


@_strumento
def converti_preventivo_in_ordine(numero: str) -> dict:
    """Converte un preventivo in ordine cliente: copia testata e righe e segna il preventivo come
    convertito."""
    from apps.sales import services as sales_services
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    ordine = sales_services.convert_quote_to_order(preventivo)
    return {
        "messaggio": f"Ordine {ordine.number} creato dal preventivo {preventivo.number}.",
        **_riepilogo(ordine),
        "da_preventivo": preventivo.number,
    }


# ========================================================= ordini cliente
@_strumento
def crea_ordine_cliente(
    cliente: str,
    righe: list,
    data: str = "",
    consegna_prevista: str = "",
    riferimento: str = "",
    note: str = "",
    condizioni: str = "",
    pagamento: str = "",
    cantiere: str = "",
    provvigione_a: str = "",
    provvigione_pct: float = 0,
) -> dict:
    """Crea un ordine cliente in bozza. righe ha lo stesso formato di crea_preventivo."""
    from django.db import transaction
    from django.utils import timezone

    from apps.sales.models import SalesOrder, SalesOrderLine

    righe_valide = _normalizza_righe(righe)
    with transaction.atomic():
        ordine = SalesOrder(
            customer=_risolvi_contatto(cliente),
            date=_data(data) or timezone.localdate(),
            expected_date=_data(consegna_prevista, "consegna_prevista"),
            reference=(riferimento or "").strip(),
            notes=note or "",
            terms_text=condizioni or "",
        )
        if pagamento:
            ordine.payment_term = _risolvi_pagamento(pagamento)
        if cantiere:
            ordine.job = _risolvi_cantiere(cantiere)
        if provvigione_a:
            ordine.commission_contact = _risolvi_contatto(provvigione_a)
            ordine.commission_pct = _dec(provvigione_pct)
        ordine.save()
        numero_righe = _crea_righe(SalesOrderLine, "order", ordine, righe_valide, uso="vendita")
        ordine.recalculate()
    return {"messaggio": f"Ordine {ordine.number} creato in bozza.", **_riepilogo(ordine), "righe_create": numero_righe}


@_strumento
def conferma_ordine(numero: str, rifornisci: bool = False) -> dict:
    """Conferma un ordine cliente: fissa i costi per la marginalità ed eventualmente genera gli
    ordini fornitore per le quantità mancanti. Con rifornisci=True riporta le giacenze a scorta
    minima negli ordini fornitore generati."""
    from apps.sales import services as sales_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero, "ordine")
    esito = sales_services.confirm_sales_order(ordine, replenish=bool(rifornisci))
    ordine.refresh_from_db()
    return {
        "messaggio": f"Ordine {ordine.number} confermato.",
        **_riepilogo(ordine),
        "stato": ordine.get_status_display(),
        "ordini_fornitore_generati": [str(po) for po in esito.get("purchase_orders", [])],
        "articoli_senza_fornitore": [str(p) for p in esito.get("without_supplier", [])],
    }


@_strumento
def registra_consegna_ordine(numero: str, magazzino: str = "") -> dict:
    """Registra la consegna di un ordine cliente: consegna tutte le quantità residue e, per gli
    articoli gestiti a magazzino, registra gli scarichi. Se tutto è consegnato l'ordine passa a
    «Consegnato»."""
    from apps.sales import services as sales_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero, "ordine")
    warehouse = _risolvi_magazzino(magazzino) if magazzino else None
    errori = sales_services.deliver_sales_order(ordine, warehouse=warehouse)
    ordine.refresh_from_db()
    return {
        "messaggio": f"Consegna registrata per l'ordine {ordine.number}.",
        **_riepilogo(ordine),
        "stato": ordine.get_status_display(),
        "consegnato_il": _valore(ordine.delivered_at),
        "avvisi": errori,
    }


# ===================================================================== DDT
@_strumento
def crea_ddt_da_ordine(numero_ordine: str) -> dict:
    """Crea un DDT in bozza dalle quantità ancora da consegnare di un ordine cliente."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    ddt = billing_services.create_delivery_note_from_order(ordine)
    return {
        "messaggio": f"DDT {ddt.number} creato dall'ordine {ordine.number}.",
        "numero": ddt.number,
        "data": _valore(ddt.date),
        "cliente": ddt.customer.name,
    }


@_strumento
def emetti_ddt(numero: str, magazzino: str = "") -> dict:
    """Emette un DDT: scarica la merce dal magazzino, aggiorna le quantità consegnate
    dell'ordine collegato e, se l'ordine risulta completo, lo segna come consegnato."""
    from apps.billing import services as billing_services
    from apps.billing.models import DeliveryNote

    ddt = _risolvi_documento(DeliveryNote, numero, "DDT")
    warehouse = _risolvi_magazzino(magazzino) if magazzino else None
    errori = billing_services.issue_delivery_note(ddt, warehouse=warehouse)
    ddt.refresh_from_db()
    return {
        "messaggio": f"DDT {ddt.number} emesso.",
        "numero": ddt.number,
        "stato": ddt.get_status_display(),
        "emesso_il": _valore(ddt.issued_at),
        "avvisi": errori,
    }


# ============================================================ fatture emesse
@_strumento
def crea_fattura_da_ordine(numero_ordine: str, solo_consegnate: bool = False) -> dict:
    """Crea una fattura emessa in bozza da un ordine cliente. Con solo_consegnate=True fattura solo
    le quantità già consegnate."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    fattura = billing_services.create_sales_invoice_from_order(ordine, only_delivered=bool(solo_consegnate))
    return {"messaggio": f"Fattura {fattura.number} creata dall'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento
def crea_fattura_da_ddt(numero_ddt: str) -> dict:
    """Crea una fattura emessa in bozza da un DDT già emesso."""
    from apps.billing import services as billing_services
    from apps.billing.models import DeliveryNote

    ddt = _risolvi_documento(DeliveryNote, numero_ddt, "DDT")
    fattura = billing_services.create_sales_invoice_from_delivery_note(ddt)
    return {"messaggio": f"Fattura {fattura.number} creata dal DDT {ddt.number}.", **_riepilogo(fattura)}


@_strumento
def crea_acconto_ordine(
    numero_ordine: str, percentuale: Optional[float] = None, importo: Optional[float] = None
) -> dict:
    """Crea la fattura di acconto su un ordine cliente, in percentuale sull'imponibile oppure a
    importo fisso: specificare percentuale oppure importo (uno dei due)."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    if (percentuale is None) == (importo is None):
        raise ValueError("Specificare percentuale oppure importo (uno dei due).")
    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    fattura = billing_services.create_order_advance(
        ordine,
        percent=_dec(percentuale) if percentuale is not None else None,
        amount=_dec(importo) if importo is not None else None,
    )
    return {"messaggio": f"Acconto {fattura.number} creato sull'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento
def crea_saldo_ordine(numero_ordine: str) -> dict:
    """Crea la fattura di saldo di un ordine cliente, scalando gli eventuali acconti già emessi."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    fattura = billing_services.create_order_balance(ordine)
    return {"messaggio": f"Saldo {fattura.number} creato sull'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento
def emetti_fattura(numero: str) -> dict:
    """Passa una fattura emessa da bozza a emessa."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    fattura = _risolvi_documento(SalesInvoice, numero, "fattura")
    billing_services.issue_sales_invoice(fattura)
    fattura.refresh_from_db()
    return {"messaggio": f"Fattura {fattura.number} emessa.", "numero": fattura.number, "stato": fattura.get_status_display()}


@_strumento
def segna_fattura_inviata(numero: str) -> dict:
    """Segna una fattura emessa come inviata al cliente."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    fattura = _risolvi_documento(SalesInvoice, numero, "fattura")
    billing_services.mark_sales_invoice_sent(fattura)
    fattura.refresh_from_db()
    return {"messaggio": f"Fattura {fattura.number} inviata.", "numero": fattura.number, "stato": fattura.get_status_display()}


@_strumento
def segna_fattura_pagata(numero: str) -> dict:
    """Segna una fattura emessa come pagata."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    fattura = _risolvi_documento(SalesInvoice, numero, "fattura")
    billing_services.mark_sales_invoice_paid(fattura)
    fattura.refresh_from_db()
    return {
        "messaggio": f"Fattura {fattura.number} pagata.",
        "numero": fattura.number,
        "stato": fattura.get_status_display(),
        "pagata_il": _valore(fattura.paid_at),
    }


# ======================================================= fatture ricevute
@_strumento
def crea_fattura_ricevuta_da_ordine_fornitore(numero_ordine: str, solo_ricevute: bool = False) -> dict:
    """Crea in bozza una fattura ricevuta da un ordine fornitore. Con solo_ricevute=True considera
    solo le quantità già ricevute."""
    from apps.billing import services as billing_services
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero_ordine, "ordine fornitore")
    fattura = billing_services.create_purchase_invoice_from_po(ordine, only_received=bool(solo_ricevute))
    return {
        "messaggio": f"Fattura ricevuta {fattura.number} creata dall'ordine {ordine.number}.",
        **_riepilogo(fattura),
        "fornitore": fattura.supplier.name,
    }


@_strumento
def registra_fattura_ricevuta(numero: str) -> dict:
    """Registra una fattura ricevuta: passa da bozza a da pagare."""
    from apps.billing import services as billing_services
    from apps.billing.models import PurchaseInvoice

    fattura = _risolvi_documento(PurchaseInvoice, numero, "fattura ricevuta")
    billing_services.register_purchase_invoice(fattura)
    fattura.refresh_from_db()
    return {
        "messaggio": f"Fattura ricevuta {fattura.number} registrata.",
        "numero": fattura.number,
        "stato": fattura.get_status_display(),
        "scadenza": _valore(fattura.due_date),
    }


@_strumento
def segna_fattura_ricevuta_pagata(numero: str) -> dict:
    """Segna una fattura ricevuta come pagata."""
    from apps.billing import services as billing_services
    from apps.billing.models import PurchaseInvoice

    fattura = _risolvi_documento(PurchaseInvoice, numero, "fattura ricevuta")
    billing_services.mark_purchase_invoice_paid(fattura)
    fattura.refresh_from_db()
    return {
        "messaggio": f"Fattura ricevuta {fattura.number} pagata.",
        "numero": fattura.number,
        "stato": fattura.get_status_display(),
        "pagata_il": _valore(fattura.paid_at),
    }


# ========================================================= ordini fornitore
@_strumento
def crea_ordine_fornitore(
    fornitore: str,
    righe: list,
    data: str = "",
    consegna_prevista: str = "",
    cantiere: str = "",
    ordine_cliente: str = "",
    pagamento: str = "",
    note: str = "",
) -> dict:
    """Crea un ordine fornitore. righe ha lo stesso formato di crea_preventivo (prezzo e IVA
    predefiniti sono quelli di acquisto). ordine_cliente è opzionale e collega l'ordine cliente
    di origine."""
    from django.db import transaction
    from django.utils import timezone

    from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
    from apps.sales.models import SalesOrder

    righe_valide = _normalizza_righe(righe)
    with transaction.atomic():
        ordine = PurchaseOrder(
            supplier=_risolvi_contatto(fornitore),
            date=_data(data) or timezone.localdate(),
            expected_date=_data(consegna_prevista, "consegna_prevista"),
            notes=note or "",
        )
        if pagamento:
            ordine.payment_term = _risolvi_pagamento(pagamento)
        if cantiere:
            ordine.job = _risolvi_cantiere(cantiere)
        if ordine_cliente:
            ordine.source_sales_order = _risolvi_documento(SalesOrder, ordine_cliente, "ordine")
        ordine.save()
        numero_righe = _crea_righe(PurchaseOrderLine, "po", ordine, righe_valide, uso="acquisto")
        ordine.recalculate()
    return {
        "messaggio": f"Ordine fornitore {ordine.number} creato.",
        **_riepilogo(ordine),
        "fornitore": ordine.supplier.name,
        "righe_create": numero_righe,
    }


@_strumento
def ricevi_ordine_fornitore(numero: str, magazzino: str = "", righe: Optional[list] = None) -> dict:
    """Registra la ricezione di un ordine fornitore e carica la merce a magazzino. Senza righe
    riceve tutte le quantità residue; con righe (lista di {posizione, quantita}) riceve solo le
    quantità indicate per posizione di riga."""
    from apps.purchasing import services as purchasing_services
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero, "ordine fornitore")
    if not ordine.can_receive:
        raise ValueError(f"L'ordine {ordine.number} non è in uno stato che consente la ricezione.")
    quantities = {}
    if righe:
        for voce in righe:
            if not isinstance(voce, dict) or "posizione" not in voce:
                raise ValueError("Ogni elemento di righe deve essere un dizionario {posizione, quantita}.")
            try:
                posizione = int(voce["posizione"])
            except (TypeError, ValueError):
                raise ValueError(f"Posizione di riga non valida: {voce.get('posizione')!r}.")
            linea = ordine.lines.filter(position=posizione).first()
            if linea is None:
                raise ValueError(f"L'ordine {ordine.number} non ha righe in posizione {posizione}.")
            quantities[str(linea.pk)] = _dec(voce.get("quantita", 0))
    else:
        for linea in ordine.lines.all():
            if not linea.is_display and linea.qty_remaining > 0:
                quantities[str(linea.pk)] = linea.qty_remaining
    if not quantities:
        raise ValueError(f"L'ordine {ordine.number} non ha quantità da ricevere.")
    warehouse = _risolvi_magazzino(magazzino) if magazzino else None
    ricevute, errori = purchasing_services.receive_purchase_order(ordine, quantities, warehouse=warehouse)
    ordine.refresh_from_db()
    return {
        "messaggio": f"Ricezione registrata per l'ordine {ordine.number}.",
        "numero": ordine.number,
        "stato": ordine.get_status_display(),
        "righe_ricevute": len(ricevute),
        "avvisi": errori,
    }


# ============================================== commesse, lead, manutenzioni
@_strumento
def crea_cantiere(
    cliente: str,
    nome: str,
    indirizzo: str = "",
    cap: str = "",
    citta: str = "",
    provincia: str = "",
    inizio: str = "",
    fine_prevista: str = "",
    responsabile: str = "",
    note: str = "",
) -> dict:
    """Crea un cantiere/commessa. responsabile è lo username di un utente (opzionale)."""
    from apps.jobs.models import Job

    cantiere = Job(
        customer=_risolvi_contatto(cliente),
        name=(nome or "").strip(),
        address=(indirizzo or "").strip(),
        zip_code=(cap or "").strip(),
        city=(citta or "").strip(),
        province=(provincia or "").strip(),
        start_date=_data(inizio, "inizio"),
        end_date=_data(fine_prevista, "fine_prevista"),
        notes=note or "",
    )
    if not cantiere.name:
        raise ValueError("Il nome del cantiere è obbligatorio.")
    if responsabile:
        cantiere.manager = _risolvi_utente(responsabile)
    cantiere.save()
    return {
        "messaggio": f"Cantiere {cantiere.code} creato.",
        "codice": cantiere.code,
        "nome": cantiere.name,
        "cliente": cantiere.customer.name,
    }


@_strumento
def crea_lead(
    nome: str,
    fase: str = "",
    contatto: str = "",
    telefono: str = "",
    email: str = "",
    citta: str = "",
    provenienza: str = "",
    valore_stimato: float = 0,
    prossima_azione: str = "",
    note: str = "",
) -> dict:
    """Crea un lead commerciale. fase è opzionale (altrimenti la prima fase in corso);
    contatto è un cliente/fornitore esistente (opzionale)."""
    from apps.leads.models import Lead, LeadStage

    lead = Lead(
        name=(nome or "").strip(),
        phone=(telefono or "").strip(),
        email=(email or "").strip(),
        city=(citta or "").strip(),
        source=(provenienza or "").strip(),
        estimated_value=_dec(valore_stimato),
        next_action=_data(prossima_azione, "prossima_azione"),
        notes=note or "",
    )
    if not lead.name:
        raise ValueError("Il nome del lead è obbligatorio.")
    if fase:
        lead.stage = _risolvi_fase(fase)
    else:
        lead.stage = LeadStage.objects.filter(kind=LeadStage.KIND_OPEN).order_by("order").first()
        if lead.stage is None:
            lead.stage = LeadStage.objects.order_by("order").first()
        if lead.stage is None:
            raise ValueError("Nessuna fase lead configurata: creane almeno una nelle impostazioni.")
    if contatto:
        lead.contact = _risolvi_contatto(contatto)
    lead.save()
    return {
        "messaggio": f"Lead «{lead.name}» creato.",
        "nome": lead.name,
        "fase": lead.stage.name,
        "valore_stimato": _valore(lead.estimated_value),
    }


@_strumento
def cambia_fase_lead(nome_lead: str, fase: str) -> dict:
    """Cambia la fase di un lead. fase può essere il nome di una fase oppure «avanti» per passare
    automaticamente alla fase successiva (o a vinta se si è all'ultima)."""
    from apps.leads.models import Lead

    lead = _risolvi_lead(nome_lead)
    if (fase or "").strip().lower() in {"avanti", "next", "prossima"}:
        nuova = lead.next_stage()
        if nuova is None:
            raise ValueError(f"Il lead «{lead.name}» è già chiuso ({lead.stage.get_kind_display()}).")
    else:
        nuova = _risolvi_fase(fase)
        if not lead.is_open and nuova.pk != lead.stage_id:
            raise ValueError(f"Il lead «{lead.name}» è già chiuso ({lead.stage.get_kind_display()}).")
    if nuova.pk != lead.stage_id:
        lead.stage = nuova
        lead.save(update_fields=["stage", "updated_at"])
    return {
        "messaggio": f"Lead «{lead.name}»: fase «{lead.stage.name}».",
        "nome": lead.name,
        "fase": lead.stage.name,
        "esito": lead.stage.get_kind_display(),
    }


@_strumento
def registra_manutenzione(descrizione: str, cliente: str = "") -> dict:
    """Segna una manutenzione programmata come eseguita e ne sposta la prossima esecuzione in
    base alla frequenza."""
    from apps.jobs.models import MaintenancePlan

    descrizione = (descrizione or "").strip()
    if not descrizione:
        raise ValueError("Specificare la manutenzione (descrizione o parte di essa).")
    piani = MaintenancePlan.objects.filter(active=True, name__icontains=descrizione)
    if cliente:
        piani = piani.filter(customer__name__icontains=cliente.strip())
    candidati = list(piani[:5])
    if not candidati:
        raise ValueError(f"Nessuna manutenzione attiva che contiene {descrizione!r}.")
    if len(candidati) > 1:
        elenco = ", ".join(f"{p.name} ({p.customer.name})" for p in candidati)
        raise ValueError(f"Più manutenzioni trovate: {elenco}. Specifica meglio o indica il cliente.")
    piano = candidati[0]
    prossima = piano.advance()
    return {
        "messaggio": f"Manutenzione «{piano.name}» registrata.",
        "cliente": piano.customer.name,
        "frequenza": piano.get_frequency_display(),
        "prossima_esecuzione": _valore(prossima),
    }
