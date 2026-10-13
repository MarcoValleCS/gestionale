"""Strumenti MCP del gestionale in sola lettura.

Coprono l'intero perimetro del gestionale: anagrafiche, preventivi, ordini
cliente, DDT, fatture emesse e ricevute, ordini fornitore, magazzino,
catalogo, commesse, lead, personale e impostazioni. Tutte le funzioni leggono
soltanto il database.
"""
from typing import Annotated

from pydantic import Field

from mcp_common import (
    LETTURA,
    DataA,
    DataDa,
    Limite50,
    Limite200,
    Offset,
    _intervallo,
    _limite,
    _metadati,
    _offset,
    _pagina,
    _riga,
    _righe_documento,
    _stato_codice,
    _strumento,
    _totali,
    _valore,
)


def _oggi():
    from django.utils import timezone

    return timezone.localdate()


# ============================================================== anagrafiche
@_strumento(annotazioni=LETTURA)
def cerca_clienti(
    testo: Annotated[str, Field(description="Testo da cercare (nome, codice, città, email o P.IVA; almeno 2 caratteri).")],
    limite: Limite50 = 10,
    offset: Offset = 0,
) -> dict:
    """Cerca clienti e fornitori per nome, codice, città, email o P.IVA."""
    from django.db.models import Q

    from apps.contacts.models import Contact

    testo = (testo or "").strip()
    if len(testo) < 2:
        return {"errore": "Scrivi almeno 2 caratteri."}
    inizio = _offset(offset)
    massimo = _limite(limite)
    contatti = (
        Contact.objects.filter(
            Q(name__icontains=testo)
            | Q(code__icontains=testo)
            | Q(city__icontains=testo)
            | Q(email__icontains=testo)
            | Q(vat_number__icontains=testo)
        )
        .order_by("name")
    )
    elenco = [
        {
            **_riga(c, "code", "name", "city", "email", "phone", "vat_number"),
            "cliente": c.is_customer,
            "fornitore": c.is_supplier,
        }
        for c in contatti[inizio : inizio + massimo]
    ]
    return _pagina(elenco, contatti.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def scheda_cliente(codice: Annotated[str, Field(description="Codice esatto del contatto.")]) -> dict:
    """Scheda anagrafica di un cliente (per codice) con documenti aperti e fatture da incassare."""
    from apps.billing.models import SalesInvoice
    from apps.contacts.models import Contact
    from apps.sales.models import Quote, SalesOrder

    contatto = Contact.objects.filter(code=(codice or "").strip()).first()
    if contatto is None:
        return {"errore": f"Nessun contatto con codice {codice!r}."}
    oggi = _oggi()

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
                "numero": f.number,
                "data": _valore(f.date),
                "scadenza": _valore(f.due_date),
                "stato": f.get_status_display(),
                "imponibile": _valore(f.subtotal),
                "totale": _valore(f.grand_total),
                "scaduta": bool(f.due_date and f.due_date < oggi),
            }
            for f in fatture
        ],
    }


@_strumento(annotazioni=LETTURA)
def dati_azienda() -> dict:
    """Dati anagrafici dell'azienda (nome, P.IVA, indirizzo, contatti, IBAN)."""
    from apps.core.models import CompanySettings

    azienda = CompanySettings.load()
    return _riga(
        azienda, "name", "vat_number", "tax_code", "pec", "fiscal_regime", "address",
        "zip_code", "city", "province", "country", "email", "phone", "website", "iban",
    )


@_strumento(annotazioni=LETTURA)
def lista_termini_pagamento() -> dict:
    """Elenca le condizioni di pagamento (nome, giorni, fine mese)."""
    from apps.core.models import PaymentTerm

    elenco = [
        {"nome": t.name, "giorni": t.days, "fine_mese": t.end_of_month, "note": t.notes}
        for t in PaymentTerm.objects.order_by("days", "name")
    ]
    return _pagina(elenco, len(elenco), 0, len(elenco))


# ================================================================ preventivi
@_strumento(annotazioni=LETTURA)
def lista_preventivi(
    stato: Annotated[str, Field(description="Stato del preventivo (bozza, inviato, accettato, rifiutato, convertito); vuoto = tutti.")] = "",
    cliente: Annotated[str, Field(description="Parte del nome del cliente; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca preventivi, più recenti prima. Stato: bozza, inviato, accettato, rifiutato, convertito
    (o vuoto). Filtro per cliente (parte del nome) e intervallo di date (da_data, a_data)."""
    from apps.sales.models import Quote

    da, a = _intervallo(da_data, a_data)
    righe = Quote.objects.select_related("customer").order_by("-date", "-pk")
    codice_stato = _stato_codice(stato, Quote.STATUS_CHOICES)
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if (cliente or "").strip():
        righe = righe.filter(customer__name__icontains=cliente.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": q.number,
            "data": _valore(q.date),
            "valido_fino_al": _valore(q.valid_until),
            "cliente": q.customer.name,
            "stato": q.get_status_display(),
            "imponibile": _valore(q.subtotal),
            "totale": _valore(q.grand_total),
        }
        for q in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_preventivo(numero: Annotated[str, Field(description="Numero esatto del preventivo.")]) -> dict:
    """Dettaglio di un preventivo per numero: testata, righe e totali."""
    from apps.sales.models import Quote

    preventivo = (
        Quote.objects.select_related("customer", "payment_term", "job", "commission_contact")
        .filter(number=(numero or "").strip())
        .first()
    )
    if preventivo is None:
        return {"errore": f"Nessun preventivo con numero {numero!r}."}
    return {
        "numero": preventivo.number,
        "data": _valore(preventivo.date),
        "valido_fino_al": _valore(preventivo.valid_until),
        "stato": preventivo.get_status_display(),
        "cliente": preventivo.customer.name,
        "cantiere": preventivo.job.name if preventivo.job_id else "",
        "pagamento": preventivo.payment_term.name if preventivo.payment_term_id else "",
        "riferimento": preventivo.reference or "",
        "scaduto": preventivo.is_expired,
        "righe": _righe_documento(preventivo),
        **_totali(preventivo),
    }


@_strumento(annotazioni=LETTURA)
def preventivi_in_scadenza(
    giorni: Annotated[int, Field(ge=0, le=365, description="Giorni di preavviso da oggi (0-365).")] = 7,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Preventivi ancora aperti (bozza o inviati) con la validità scaduta o in scadenza entro N giorni."""
    from datetime import timedelta

    from apps.sales.models import Quote

    oggi = _oggi()
    try:
        giorni = max(0, int(giorni))
    except (TypeError, ValueError):
        giorni = 7
    base = Quote.objects.filter(
        status__in=[Quote.STATUS_DRAFT, Quote.STATUS_SENT], valid_until__isnull=False
    ).select_related("customer")
    inizio = _offset(offset)
    massimo = _limite(limite)

    def _elenco(queryset):
        ordinate = queryset.order_by("valid_until")
        elenco = [
            {
                "numero": q.number,
                "data": _valore(q.date),
                "valido_fino_al": _valore(q.valid_until),
                "cliente": q.customer.name,
                "stato": q.get_status_display(),
                "totale": _valore(q.grand_total),
            }
            for q in ordinate[inizio : inizio + massimo]
        ]
        return {**_metadati(len(elenco), ordinate.count(), inizio, massimo), "elenco": elenco}

    scaduti = base.filter(valid_until__lt=oggi)
    in_scadenza = base.filter(valid_until__gte=oggi, valid_until__lte=oggi + timedelta(days=giorni))
    return {
        "entro_il": _valore(oggi + timedelta(days=giorni)),
        "preventivi_scaduti": _elenco(scaduti),
        "preventivi_in_scadenza": _elenco(in_scadenza),
    }


# ===================================================== ordini cliente (vendite)
@_strumento(annotazioni=LETTURA)
def lista_ordini(
    stato: Annotated[str, Field(description="Stato dell'ordine (bozza, confermato, consegnato, annullato); vuoto = tutti.")] = "",
    cliente: Annotated[str, Field(description="Parte del nome del cliente; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca gli ordini cliente, più recenti prima. Stato: bozza, confermato, consegnato, annullato
    (o vuoto). Filtro per cliente e intervallo di date (da_data, a_data)."""
    from apps.sales.models import SalesOrder

    da, a = _intervallo(da_data, a_data)
    codice_stato = _stato_codice(stato, SalesOrder.STATUS_CHOICES)
    righe = SalesOrder.objects.select_related("customer", "job").order_by("-date", "-pk")
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if (cliente or "").strip():
        righe = righe.filter(customer__name__icontains=cliente.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    oggi = _oggi()
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": o.number,
            "data": _valore(o.date),
            "consegna_prevista": _valore(o.expected_date),
            "cliente": o.customer.name,
            "cantiere": o.job.name if o.job_id else "",
            "stato": o.get_status_display(),
            "consegnato_il": _valore(o.delivered_at),
            "totale": _valore(o.grand_total),
            "in_ritardo": bool(o.expected_date and o.expected_date < oggi and o.delivered_at is None),
        }
        for o in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_ordine(numero: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")]) -> dict:
    """Dettaglio di un ordine cliente per numero: testata, righe con quantità consegnate/residue,
    DDT e fatture collegate, eventuale provvigione."""
    from apps.billing.models import DeliveryNote, SalesInvoice
    from apps.sales.models import SalesOrder

    ordine = (
        SalesOrder.objects.select_related("customer", "payment_term", "job", "source_quote", "commission_contact")
        .filter(number=(numero or "").strip())
        .first()
    )
    if ordine is None:
        return {"errore": f"Nessun ordine con numero {numero!r}."}
    stati_consegna = {"delivered": "Consegnato", "partially": "Parzialmente consegnato"}
    residui = [
        {
            "articolo": riga.product.code if riga.product_id else "",
            "descrizione": riga.label,
            "quantita_residua": _valore(riga.qty_remaining),
        }
        for riga in ordine.lines.all()
        if not riga.is_display and riga.qty_remaining > 0
    ]
    ddt = list(DeliveryNote.objects.filter(source_order=ordine).order_by("-date").values_list("number", flat=True))
    fatture = list(SalesInvoice.objects.filter(source_order=ordine).order_by("-date").values_list("number", flat=True))
    esito = {
        "numero": ordine.number,
        "data": _valore(ordine.date),
        "consegna_prevista": _valore(ordine.expected_date),
        "stato": ordine.get_status_display(),
        "confermato_il": _valore(ordine.confirmed_at),
        "consegnato_il": _valore(ordine.delivered_at),
        "stato_consegna": stati_consegna.get(ordine.delivery_state, ordine.get_status_display()),
        "cliente": ordine.customer.name,
        "cantiere": ordine.job.name if ordine.job_id else "",
        "pagamento": ordine.payment_term.name if ordine.payment_term_id else "",
        "riferimento": ordine.reference or "",
        "da_preventivo": ordine.source_quote.number if ordine.source_quote_id else "",
        "righe": _righe_documento(ordine),
        "righe_da_consegnare": residui,
        "ddt_collegati": ddt,
        "fatture_collegate": fatture,
        **_totali(ordine),
    }
    if ordine.has_commission:
        esito["provvigione"] = {
            "a": ordine.commission_contact.name,
            "pct": _valore(ordine.commission_pct),
            "importo": _valore(ordine.commission_amount),
        }
        esito["margine_dopo_provvigione"] = _valore(ordine.margin_after_commission)
    return esito


@_strumento(annotazioni=LETTURA)
def ordini_da_consegnare(
    solo_in_ritardo: Annotated[bool, Field(description="True per i soli ordini oltre la consegna prevista.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Ordini confermati e non ancora consegnati, con le quantità residue per riga.
    Con solo_in_ritardo=True solo quelli oltre la consegna prevista."""
    from apps.sales.models import SalesOrder

    oggi = _oggi()
    ordini = (
        SalesOrder.objects.filter(status=SalesOrder.STATUS_CONFIRMED, delivered_at__isnull=True)
        .select_related("customer")
        .order_by("expected_date", "date")
    )
    if solo_in_ritardo:
        ordini = ordini.filter(expected_date__lt=oggi)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = []
    for o in ordini[inizio : inizio + massimo]:
        residui = [
            {
                "articolo": riga.product.code if riga.product_id else "",
                "descrizione": riga.label,
                "ordinata": _valore(riga.qty),
                "consegnata": _valore(riga.qty_delivered),
                "residua": _valore(riga.qty_remaining),
            }
            for riga in o.lines.all()
            if not riga.is_display and riga.qty_remaining > 0
        ]
        elenco.append(
            {
                "numero": o.number,
                "data": _valore(o.date),
                "consegna_prevista": _valore(o.expected_date),
                "cliente": o.customer.name,
                "in_ritardo": bool(o.expected_date and o.expected_date < oggi),
                "totale": _valore(o.grand_total),
                "righe_da_consegnare": residui,
            }
        )
    totale = ordini.count()
    return {
        **_metadati(len(elenco), totale, inizio, massimo),
        "totale_ordini": totale,
        "filtro": "solo in ritardo" if solo_in_ritardo else "tutti quelli confermati non consegnati",
        "ordini": elenco,
    }


# ======================================================================= DDT
@_strumento(annotazioni=LETTURA)
def lista_ddt(
    stato: Annotated[str, Field(description="Stato del DDT (bozza, emesso, annullato); vuoto = tutti.")] = "",
    cliente: Annotated[str, Field(description="Parte del nome del cliente; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca i DDT in uscita, più recenti prima. Stato: bozza, emesso, annullato (o vuoto).
    Filtro per cliente e intervallo di date (da_data, a_data)."""
    from apps.billing.models import DeliveryNote

    da, a = _intervallo(da_data, a_data)
    codice_stato = _stato_codice(stato, DeliveryNote.STATUS_CHOICES)
    righe = DeliveryNote.objects.select_related("customer", "source_order").order_by("-date", "-pk")
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if (cliente or "").strip():
        righe = righe.filter(customer__name__icontains=cliente.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": d.number,
            "data": _valore(d.date),
            "cliente": d.customer.name,
            "stato": d.get_status_display(),
            "fatturato": d.invoiced,
            "ordine": d.source_order.number if d.source_order_id else "",
            "colli": d.packages,
            "vettore": d.carrier,
        }
        for d in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_ddt(numero: Annotated[str, Field(description="Numero esatto del DDT.")]) -> dict:
    """Dettaglio di un DDT per numero: testata, righe, destinazione e ordine collegato."""
    from apps.billing.models import DeliveryNote

    ddt = (
        DeliveryNote.objects.select_related("customer", "job", "source_order")
        .filter(number=(numero or "").strip())
        .first()
    )
    if ddt is None:
        return {"errore": f"Nessun DDT con numero {numero!r}."}
    return {
        "numero": ddt.number,
        "data": _valore(ddt.date),
        "stato": ddt.get_status_display(),
        "emesso_il": _valore(ddt.issued_at),
        "cliente": ddt.customer.name,
        "cantiere": ddt.job.name if ddt.job_id else "",
        "ordine": ddt.source_order.number if ddt.source_order_id else "",
        "fatturato": ddt.invoiced,
        "causale_trasporto": ddt.transport_reason,
        "vettore": ddt.carrier,
        "colli": ddt.packages,
        "peso_kg": _valore(ddt.weight),
        "destinazione": ddt.destination_address,
        "righe": _righe_documento(ddt),
    }


@_strumento(annotazioni=LETTURA)
def ddt_da_fatturare(limite: Limite50 = 20, offset: Offset = 0) -> dict:
    """DDT emessi e non ancora fatturati, in ordine di data."""
    from apps.billing.models import DeliveryNote

    ddt = (
        DeliveryNote.objects.filter(status=DeliveryNote.STATUS_ISSUED, invoiced=False)
        .select_related("customer", "source_order")
        .order_by("date")
    )
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": d.number,
            "data": _valore(d.date),
            "cliente": d.customer.name,
            "ordine": d.source_order.number if d.source_order_id else "",
            "totale_quantita": _valore(d.total_qty),
        }
        for d in ddt[inizio : inizio + massimo]
    ]
    return _pagina(elenco, ddt.count(), inizio, massimo)


# ========================================================== fatture emesse
@_strumento(annotazioni=LETTURA)
def fatture_da_incassare(
    solo_scadute: Annotated[bool, Field(description="True per le sole fatture oltre la scadenza.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Fatture emesse non pagate (inviate o emesse), con flag scadute."""
    from apps.billing.models import SalesInvoice

    oggi = _oggi()
    fatture = SalesInvoice.objects.filter(
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT]
    ).select_related("customer")
    if solo_scadute:
        fatture = fatture.filter(due_date__lt=oggi)
    inizio = _offset(offset)
    massimo = _limite(limite)
    fatture = fatture.order_by("due_date")
    elenco = [
        {
            "numero": f.number,
            "data": _valore(f.date),
            "scadenza": _valore(f.due_date),
            "cliente": f.customer.name,
            "imponibile": _valore(f.subtotal),
            "totale": _valore(f.grand_total),
            "stato": f.get_status_display(),
            "scaduta": bool(f.due_date and f.due_date < oggi),
        }
        for f in fatture[inizio : inizio + massimo]
    ]
    return _pagina(elenco, fatture.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def lista_fatture(
    stato: Annotated[str, Field(description="Stato della fattura (bozza, emessa, inviata, pagata, annullata); vuoto = tutte.")] = "",
    cliente: Annotated[str, Field(description="Parte del nome del cliente; vuoto = tutte.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    solo_scadute: Annotated[bool, Field(description="True per le sole fatture scadute e non pagate.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca le fatture emesse, più recenti prima. Stato: bozza, emessa, inviata, pagata, annullata
    (o vuoto). Filtri per cliente, intervallo di date (da_data, a_data) e solo_scadute."""
    from apps.billing.models import SalesInvoice

    da, a = _intervallo(da_data, a_data)
    codice_stato = _stato_codice(stato, SalesInvoice.STATUS_CHOICES)
    oggi = _oggi()
    righe = SalesInvoice.objects.select_related("customer", "job").order_by("-date", "-pk")
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if solo_scadute:
        righe = righe.filter(status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT], due_date__lt=oggi)
    if (cliente or "").strip():
        righe = righe.filter(customer__name__icontains=cliente.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": f.number,
            "data": _valore(f.date),
            "scadenza": _valore(f.due_date),
            "cliente": f.customer.name,
            "cantiere": f.job.name if f.job_id else "",
            "tipo": f.kind_title,
            "stato": f.get_status_display(),
            "scaduta": f.is_overdue,
            "totale": _valore(f.grand_total),
        }
        for f in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_fattura(numero: Annotated[str, Field(description="Numero esatto della fattura emessa.")]) -> dict:
    """Dettaglio di una fattura emessa per numero: testata, righe, riepilogo IVA, stato SDI e
    documenti di origine."""
    from apps.billing.models import SalesInvoice

    fattura = (
        SalesInvoice.objects.select_related("customer", "payment_term", "job", "source_order", "source_delivery_note")
        .filter(number=(numero or "").strip())
        .first()
    )
    if fattura is None:
        return {"errore": f"Nessuna fattura con numero {numero!r}."}
    return {
        "numero": fattura.number,
        "data": _valore(fattura.date),
        "scadenza": _valore(fattura.due_date),
        "scaduta": fattura.is_overdue,
        "stato": fattura.get_status_display(),
        "tipo": fattura.kind_title,
        "cliente": fattura.customer.name,
        "cantiere": fattura.job.name if fattura.job_id else "",
        "pagamento": fattura.payment_term.name if fattura.payment_term_id else "",
        "riferimento": fattura.reference or "",
        "da_ordine": fattura.source_order.number if fattura.source_order_id else "",
        "da_ddt": fattura.source_delivery_note.number if fattura.source_delivery_note_id else "",
        "emessa_il": _valore(fattura.issued_at),
        "inviata_il": _valore(fattura.sent_at),
        "pagata_il": _valore(fattura.paid_at),
        "stato_sdi": fattura.get_sdi_status_display(),
        "righe": _righe_documento(fattura),
        "riepilogo_iva": [
            {"aliquota": str(v["rate"].rate), "imponibile": _valore(v["base"]), "iva": _valore(v["vat"])}
            for v in fattura.vat_breakdown()
        ],
        **_totali(fattura),
    }


@_strumento(annotazioni=LETTURA)
def fatturato_periodo(da_data: DataDa = "", a_data: DataA = "") -> dict:
    """Fatturato emesso in un periodo (default: mese corrente): totale, ripartizione per mese e per
    tipo di documento (fattura, acconto, SAL, saldo)."""
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth

    from apps.billing.models import SalesInvoice

    oggi = _oggi()
    da, a = _intervallo(da_data, a_data)
    da = da or oggi.replace(day=1)
    a = a or oggi
    fatturato = SalesInvoice.objects.filter(
        date__gte=da,
        date__lte=a,
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT, SalesInvoice.STATUS_PAID],
    )
    totali = fatturato.aggregate(
        numero=Count("pk"), imponibile=Sum("subtotal"), iva=Sum("vat_total"), totale=Sum("grand_total")
    )
    per_mese = [
        {"mese": r["mese"].strftime("%Y-%m"), "numero": r["numero"], "totale": _valore(r["totale"])}
        for r in fatturato.annotate(mese=TruncMonth("date"))
        .values("mese")
        .annotate(numero=Count("pk"), totale=Sum("grand_total"))
        .order_by("mese")
    ]
    etichette = dict(SalesInvoice.KIND_CHOICES)
    per_tipo = [
        {"tipo": etichette.get(r["kind"], r["kind"]), "numero": r["numero"], "totale": _valore(r["totale"])}
        for r in fatturato.values("kind").annotate(numero=Count("pk"), totale=Sum("grand_total")).order_by("-totale")
    ]
    return {
        "periodo": {"da": _valore(da), "a": _valore(a)},
        "numero_documenti": totali["numero"] or 0,
        "imponibile": _valore(totali["imponibile"] or 0),
        "iva": _valore(totali["iva"] or 0),
        "totale": _valore(totali["totale"] or 0),
        "per_mese": per_mese,
        "per_tipo": per_tipo,
    }


# ============================================================== statistiche
@_strumento(annotazioni=LETTURA)
def statistiche_vendite(
    periodo: Annotated[str, Field(description="Periodo di analisi: mese, anno o 12m.")] = "mese",
    limite: Limite50 = 10,
) -> dict:
    """Statistiche di vendita per periodo: mese, anno o 12m. Fatturato, costo, provvigioni e
    margine, con le classifiche per articolo, cliente, fornitore e cantiere."""
    from apps.sales import analytics

    codici = dict(analytics.PERIOD_CHOICES)
    codice_periodo = (periodo or "mese").strip().lower()
    if codice_periodo not in codici:
        ammessi = ", ".join(f"{codice} ({etichetta})" for codice, etichetta in codici.items())
        raise ValueError(f"Periodo {periodo!r} non valido. Valori ammessi: {ammessi}.")
    dati = analytics.breakdowns(codice_periodo, limit=_limite(limite, massimo=50))

    def _classifica(righe):
        return [
            {
                "voce": riga["label"],
                "fatturato": _valore(riga["revenue"]),
                "costo": _valore(riga["cost"]),
                "provvigioni": _valore(riga["commission"]),
                "margine": _valore(riga["margin"]),
                "margine_pct": _valore(riga["margin_pct"]),
            }
            for riga in righe
        ]

    sintesi = dati["summary"]
    return {
        "periodo": codici[codice_periodo],
        "fatturato": _valore(sintesi["revenue"]),
        "costo": _valore(sintesi["cost"]),
        "provvigioni": _valore(sintesi["commission"]),
        "margine": _valore(sintesi["margin"]),
        "margine_pct": _valore(sintesi["margin_pct"]),
        "margine_prima_provvigioni": _valore(sintesi["margin_before_commission"]),
        "ordini": sintesi["orders"],
        "per_articolo": _classifica(dati["by_product"]),
        "per_cliente": _classifica(dati["by_customer"]),
        "per_fornitore": _classifica(dati["by_supplier"]),
        "per_cantiere": _classifica(dati["by_job"]),
    }


@_strumento(annotazioni=LETTURA)
def provvigioni(
    anno: Annotated[int, Field(ge=0, le=2100, description="Anno (es. 2026); 0 = anno corrente.")] = 0,
    mese: Annotated[int, Field(ge=0, le=12, description="Mese 1-12; 0 = mese corrente.")] = 0,
    stato: Annotated[str, Field(description="Stato: tutti, consegnati o confermati.")] = "tutti",
) -> dict:
    """Provvigioni maturate nel mese e nell'anno indicati (default: mese e anno correnti),
    raggruppate per beneficiario. stato: tutti, consegnati o confermati."""
    from apps.sales import analytics

    stati = {
        "tutti": analytics.STATO_TUTTI,
        "consegnati": analytics.STATO_CONSEGNATI,
        "confermati": analytics.STATO_CONFERMATI,
    }
    codice_stato = (stato or "tutti").strip().lower()
    if codice_stato not in stati:
        raise ValueError("Stato non valido: usa tutti, consegnati o confermati.")
    try:
        anno = int(anno) if anno else None
        mese = int(mese) if mese else None
    except (TypeError, ValueError):
        raise ValueError("Anno e mese devono essere numeri (es. 2026, 10).")
    report = analytics.commission_report(anno, mese, stati[codice_stato])
    annuo = analytics.commission_year(anno or report["year"], stati[codice_stato])
    return {
        "mese": report["label"],
        "stato": codice_stato,
        "totale_provvigioni": _valore(report["total_commission"]),
        "totale_maturate": _valore(report["total_paid"]),
        "totale_in_maturare": _valore(report["total_pending"]),
        "per_beneficiario": [
            {
                "beneficiario": voce["contact"].name,
                "ordini": len(voce["orders"]),
                "imponibile": _valore(voce["revenue"]),
                "provvigione": _valore(voce["commission"]),
                "maturata": _valore(voce["paid"]),
                "in_maturare": _valore(voce["pending"]),
            }
            for voce in report["rows"]
        ],
        "anno": report["year"],
        "per_beneficiario_anno": [
            {
                "beneficiario": voce["contact"].name,
                "ordini": voce["orders"],
                "imponibile": _valore(voce["revenue"]),
                "provvigione": _valore(voce["commission"]),
            }
            for voce in annuo
        ],
    }


# ===================================================== fatture ricevute (acquisti)
@_strumento(annotazioni=LETTURA)
def lista_fatture_fornitori(
    stato: Annotated[str, Field(description="Stato della fattura (bozza, da pagare, pagata, annullata); vuoto = tutte.")] = "",
    fornitore: Annotated[str, Field(description="Parte del nome del fornitore; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    solo_scadute: Annotated[bool, Field(description="True per le sole fatture scadute e non pagate.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca le fatture ricevute dai fornitori. Stato: bozza, da pagare, pagata, annullata (o vuoto).
    Filtri per fornitore, intervallo di date (da_data, a_data) e solo_scadute."""
    from apps.billing.models import PurchaseInvoice

    da, a = _intervallo(da_data, a_data)
    codice_stato = _stato_codice(stato, PurchaseInvoice.STATUS_CHOICES)
    oggi = _oggi()
    righe = PurchaseInvoice.objects.select_related("supplier", "job").order_by("-date", "-pk")
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if solo_scadute:
        righe = righe.filter(status=PurchaseInvoice.STATUS_REGISTERED, due_date__lt=oggi)
    if (fornitore or "").strip():
        righe = righe.filter(supplier__name__icontains=fornitore.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": f.number,
            "documento_fornitore": f.supplier_reference,
            "data": _valore(f.date),
            "scadenza": _valore(f.due_date),
            "fornitore": f.supplier.name,
            "stato": f.get_status_display(),
            "scaduta": bool(f.due_date and f.is_open and f.due_date < oggi),
            "totale": _valore(f.grand_total),
        }
        for f in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_fattura_fornitore(numero: Annotated[str, Field(description="Numero esatto della fattura ricevuta.")]) -> dict:
    """Dettaglio di una fattura ricevuta per numero: testata, righe e ordine collegato."""
    from apps.billing.models import PurchaseInvoice

    fattura = (
        PurchaseInvoice.objects.select_related("supplier", "payment_term", "job", "source_po")
        .filter(number=(numero or "").strip())
        .first()
    )
    if fattura is None:
        return {"errore": f"Nessuna fattura ricevuta con numero {numero!r}."}
    return {
        "numero": fattura.number,
        "documento_fornitore": fattura.supplier_reference,
        "data": _valore(fattura.date),
        "scadenza": _valore(fattura.due_date),
        "stato": fattura.get_status_display(),
        "fornitore": fattura.supplier.name,
        "cantiere": fattura.job.name if fattura.job_id else "",
        "pagamento": fattura.payment_term.name if fattura.payment_term_id else "",
        "da_ordine_fornitore": fattura.source_po.number if fattura.source_po_id else "",
        "registrata_il": _valore(fattura.registered_at),
        "pagata_il": _valore(fattura.paid_at),
        "righe": _righe_documento(fattura),
        **_totali(fattura),
    }


@_strumento(annotazioni=LETTURA)
def fatture_fornitori_da_pagare(
    solo_scadute: Annotated[bool, Field(description="True per le sole fatture oltre la scadenza.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Fatture ricevute registrate e non ancora pagate, con flag scadute."""
    from apps.billing.models import PurchaseInvoice

    oggi = _oggi()
    fatture = PurchaseInvoice.objects.filter(status=PurchaseInvoice.STATUS_REGISTERED).select_related("supplier")
    if solo_scadute:
        fatture = fatture.filter(due_date__lt=oggi)
    inizio = _offset(offset)
    massimo = _limite(limite)
    fatture = fatture.order_by("due_date")
    elenco = [
        {
            "numero": f.number,
            "documento_fornitore": f.supplier_reference,
            "data": _valore(f.date),
            "scadenza": _valore(f.due_date),
            "fornitore": f.supplier.name,
            "scaduta": bool(f.due_date and f.due_date < oggi),
            "totale": _valore(f.grand_total),
        }
        for f in fatture[inizio : inizio + massimo]
    ]
    return _pagina(elenco, fatture.count(), inizio, massimo)


# =============================================================== scadenzario
@_strumento(annotazioni=LETTURA)
def scadenzario(
    giorni: Annotated[int, Field(ge=0, le=365, description="Orizzonte in giorni da oggi (0-365).")] = 30,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Scadenzario attivo e passivo: fatture da incassare e da pagare in scadenza entro N giorni
    (default 30) e quelle già scadute, con totali."""
    from datetime import timedelta

    from django.db.models import Count, Sum

    from apps.billing.models import PurchaseInvoice, SalesInvoice

    oggi = _oggi()
    try:
        giorni = max(0, int(giorni))
    except (TypeError, ValueError):
        giorni = 30
    fino = oggi + timedelta(days=giorni)

    crediti = SalesInvoice.objects.filter(
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT], due_date__isnull=False
    ).select_related("customer")
    debiti = PurchaseInvoice.objects.filter(
        status=PurchaseInvoice.STATUS_REGISTERED, due_date__isnull=False
    ).select_related("supplier")

    inizio = _offset(offset)
    massimo = _limite(limite)

    def _elenco(queryset, fornitore=False):
        ordinate = queryset.order_by("due_date")
        elenco = []
        for f in ordinate[inizio : inizio + massimo]:
            elenco.append(
                {
                    "numero": f.number,
                    "contatto": f.supplier.name if fornitore else f.customer.name,
                    "scadenza": _valore(f.due_date),
                    "totale": _valore(f.grand_total),
                    "scaduta": bool(f.due_date and f.due_date < oggi),
                }
            )
        totale = ordinate.count()
        restituiti = len(elenco)
        return {
            "offset": inizio,
            "limite": massimo,
            "has_more": inizio + restituiti < totale,
            "prossimo_offset": inizio + restituiti if inizio + restituiti < totale else None,
            "elenco": elenco,
        }

    def _sommario(queryset):
        dati = queryset.aggregate(numero=Count("pk"), totale=Sum("grand_total"))
        return {"numero": dati["numero"] or 0, "totale": _valore(dati["totale"] or 0)}

    da_incassare = crediti.filter(due_date__gte=oggi, due_date__lte=fino)
    incassare_scaduti = crediti.filter(due_date__lt=oggi)
    da_pagare = debiti.filter(due_date__gte=oggi, due_date__lte=fino)
    pagare_scaduti = debiti.filter(due_date__lt=oggi)
    return {
        "entro_il": _valore(fino),
        "da_incassare": {**_sommario(da_incassare), **_elenco(da_incassare)},
        "da_pagare": {**_sommario(da_pagare), **_elenco(da_pagare, fornitore=True)},
        "scaduti_da_incassare": {**_sommario(incassare_scaduti), **_elenco(incassare_scaduti)},
        "scaduti_da_pagare": {**_sommario(pagare_scaduti), **_elenco(pagare_scaduti, fornitore=True)},
    }


# ========================================================== ordini fornitore
@_strumento(annotazioni=LETTURA)
def lista_ordini_fornitore(
    stato: Annotated[str, Field(description="Stato dell'ordine (bozza, inviato, confermato, parzialmente ricevuto, ricevuto, annullato); vuoto = tutti.")] = "",
    fornitore: Annotated[str, Field(description="Parte del nome del fornitore; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca gli ordini ai fornitori. Stato: bozza, inviato, confermato, parzialmente ricevuto,
    ricevuto, annullato (o vuoto). Filtri per fornitore e intervallo di date."""
    from apps.purchasing.models import PurchaseOrder

    da, a = _intervallo(da_data, a_data)
    codice_stato = _stato_codice(stato, PurchaseOrder.STATUS_CHOICES)
    righe = PurchaseOrder.objects.select_related("supplier", "job").order_by("-date", "-pk")
    if codice_stato:
        righe = righe.filter(status=codice_stato)
    if (fornitore or "").strip():
        righe = righe.filter(supplier__name__icontains=fornitore.strip())
    if da:
        righe = righe.filter(date__gte=da)
    if a:
        righe = righe.filter(date__lte=a)
    oggi = _oggi()
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "numero": o.number,
            "data": _valore(o.date),
            "consegna_prevista": _valore(o.expected_date),
            "fornitore": o.supplier.name,
            "stato": o.get_status_display(),
            "totale": _valore(o.grand_total),
            "in_ritardo": bool(o.expected_date and o.expected_date < oggi and not o.all_received),
        }
        for o in righe[inizio : inizio + massimo]
    ]
    return _pagina(elenco, righe.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_ordine_fornitore(numero: Annotated[str, Field(description="Numero esatto dell'ordine fornitore.")]) -> dict:
    """Dettaglio di un ordine fornitore per numero: testata, righe con quantità ricevute/residue."""
    from apps.purchasing.models import PurchaseOrder

    ordine = (
        PurchaseOrder.objects.select_related("supplier", "payment_term", "job", "source_sales_order")
        .filter(number=(numero or "").strip())
        .first()
    )
    if ordine is None:
        return {"errore": f"Nessun ordine fornitore con numero {numero!r}."}
    return {
        "numero": ordine.number,
        "data": _valore(ordine.date),
        "consegna_prevista": _valore(ordine.expected_date),
        "stato": ordine.get_status_display(),
        "fornitore": ordine.supplier.name,
        "cantiere": ordine.job.name if ordine.job_id else "",
        "pagamento": ordine.payment_term.name if ordine.payment_term_id else "",
        "da_ordine_cliente": ordine.source_sales_order.number if ordine.source_sales_order_id else "",
        "note": ordine.notes or "",
        "righe": _righe_documento(ordine),
        **_totali(ordine),
    }


@_strumento(annotazioni=LETTURA)
def ordini_fornitore_da_ricevere(
    solo_in_ritardo: Annotated[bool, Field(description="True per i soli ordini oltre la consegna prevista.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Ordini fornitore ancora da ricevere (bozze, inviati, confermati o parzialmente ricevuti),
    con le quantità residue. Con solo_in_ritardo=True solo quelli oltre la consegna prevista."""
    from apps.purchasing.models import PurchaseOrder

    oggi = _oggi()
    ordini = PurchaseOrder.objects.filter(
        status__in=[
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_SENT,
            PurchaseOrder.STATUS_CONFIRMED,
            PurchaseOrder.STATUS_PARTIAL,
        ]
    ).select_related("supplier")
    if solo_in_ritardo:
        ordini = ordini.filter(expected_date__lt=oggi)
    ordini = ordini.order_by("expected_date", "date")
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = []
    for o in ordini[inizio : inizio + massimo]:
        residui = [
            {
                "articolo": riga.product.code if riga.product_id else "",
                "descrizione": riga.label,
                "residua": _valore(riga.qty_remaining),
            }
            for riga in o.lines.all()
            if not riga.is_display and riga.qty_remaining > 0
        ]
        elenco.append(
            {
                "numero": o.number,
                "data": _valore(o.date),
                "consegna_prevista": _valore(o.expected_date),
                "fornitore": o.supplier.name,
                "stato": o.get_status_display(),
                "in_ritardo": bool(o.expected_date and o.expected_date < oggi),
                "righe_da_ricevere": residui,
            }
        )
    totale = ordini.count()
    return {
        **_metadati(len(elenco), totale, inizio, massimo),
        "totale_ordini": totale,
        "ordini": elenco,
    }


@_strumento(annotazioni=LETTURA)
def lista_listini(
    fornitore: Annotated[str, Field(description="Parte del nome del fornitore; vuoto = tutti.")] = "",
    solo_attivi: Annotated[bool, Field(description="True per i soli listini attivi.")] = True,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca i listini prezzi dei fornitori, con validità e numero di voci."""
    from django.db.models import Count

    from apps.purchasing.models import SupplierPriceList

    listini = SupplierPriceList.objects.select_related("supplier").annotate(voci=Count("items"))
    if (fornitore or "").strip():
        listini = listini.filter(supplier__name__icontains=fornitore.strip())
    if solo_attivi:
        listini = listini.filter(is_active=True)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "nome": l.name,
            "fornitore": l.supplier.name,
            "valido_dal": _valore(l.valid_from),
            "valido_fino_al": _valore(l.valid_to),
            "attivo": l.is_active,
            "corrente": l.is_current,
            "voci": l.voci,
        }
        for l in listini[inizio : inizio + massimo]
    ]
    return _pagina(elenco, listini.count(), inizio, massimo)


def _risolvi_listino(testo, fornitore=""):
    """Listino per nome esatto o, se univoco, per parte del nome."""
    from apps.purchasing.models import SupplierPriceList

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare il listino (nome).")
    listini = SupplierPriceList.objects.select_related("supplier").filter(name__icontains=testo)
    if (fornitore or "").strip():
        listini = listini.filter(supplier__name__icontains=fornitore.strip())
    esatto = listini.filter(name__iexact=testo).first()
    if esatto is not None:
        return esatto
    candidati = list(listini[:5])
    if not candidati:
        raise ValueError(f"Nessun listino che contiene {testo!r}.")
    if len(candidati) > 1:
        elenco = ", ".join(f"{l.name} ({l.supplier.name})" for l in candidati)
        raise ValueError(f"Più listini trovati per {testo!r}: {elenco}. Usa il nome esatto o indica il fornitore.")
    return candidati[0]


@_strumento(annotazioni=LETTURA)
def voci_listino(
    listino: Annotated[str, Field(description="Nome del listino (anche parziale, se univoco).")],
    fornitore: Annotated[str, Field(description="Parte del nome del fornitore per disambiguare; vuoto = nessun filtro.")] = "",
    limite: Limite200 = 50,
    offset: Offset = 0,
) -> dict:
    """Voci di un listino fornitore: prezzo, sconto e prezzo effettivo per articolo.
    ``listino`` è il nome (anche parziale, se univoco); ``fornitore`` restringe la ricerca."""
    prezzo_lista = _risolvi_listino(listino, fornitore)
    inizio = _offset(offset)
    massimo = _limite(limite, massimo=200)
    voci = prezzo_lista.items.select_related("product").order_by("product__name")
    elenco = [
        {
            "articolo": voce.product.code,
            "nome": voce.product.name,
            "codice_fornitore": voce.supplier_code,
            "prezzo": _valore(voce.price),
            "sconto_pct": _valore(voce.discount_pct),
            "prezzo_effettivo": _valore(voce.effective_price),
            "quantita_minima": _valore(voce.min_qty),
            "note": voce.note,
        }
        for voce in voci[inizio : inizio + massimo]
    ]
    return {
        "listino": prezzo_lista.name,
        "fornitore": prezzo_lista.supplier.name,
        "valido_dal": _valore(prezzo_lista.valid_from),
        "valido_fino_al": _valore(prezzo_lista.valid_to),
        "attivo": prezzo_lista.is_active,
        "corrente": prezzo_lista.is_current,
        "voci": elenco,
        **_metadati(len(elenco), voci.count(), inizio, massimo),
    }


# ================================================================= magazzino
@_strumento(annotazioni=LETTURA)
def lista_magazzini(solo_attivi: Annotated[bool, Field(description="True per i soli magazzini attivi.")] = True) -> dict:
    """Elenca i magazzini con la quantità complessiva giacente."""
    from django.db.models import Sum

    from apps.inventory.models import StockLevel, Warehouse

    magazzini = Warehouse.objects.all()
    if solo_attivi:
        magazzini = magazzini.filter(active=True)
    per_magazzino = {
        r["warehouse_id"]: r["totale"]
        for r in StockLevel.objects.values("warehouse_id").annotate(totale=Sum("quantity"))
    }
    elenco = [
        {
            "codice": w.code,
            "nome": w.name,
            "predefinito": w.is_default,
            "attivo": w.active,
            "quantita_totale": _valore(per_magazzino.get(w.pk, 0)),
            "note": w.address_note,
        }
        for w in magazzini
    ]
    return _pagina(elenco, len(elenco), 0, len(elenco))


@_strumento(annotazioni=LETTURA)
def giacenze(
    magazzino: Annotated[str, Field(description="Nome o codice del magazzino; vuoto = tutti.")] = "",
    articolo: Annotated[str, Field(description="Nome o codice dell'articolo; vuoto = tutti.")] = "",
    sotto_scorta: Annotated[bool, Field(description="True per i soli articoli sotto scorta minima.")] = False,
    limite: Limite200 = 50,
    offset: Offset = 0,
) -> dict:
    """Giacenze per articolo e magazzino. Filtri opzionali per magazzino (nome o codice), articolo
    (nome o codice) e per i soli articoli sotto scorta minima."""
    from django.db.models import Q

    from apps.inventory.models import StockLevel

    livelli = StockLevel.objects.select_related("product", "warehouse").order_by("product__name")
    testo_magazzino = (magazzino or "").strip()
    if testo_magazzino:
        livelli = livelli.filter(
            Q(warehouse__name__icontains=testo_magazzino) | Q(warehouse__code__icontains=testo_magazzino)
        )
    testo_articolo = (articolo or "").strip()
    if testo_articolo:
        livelli = livelli.filter(
            Q(product__name__icontains=testo_articolo) | Q(product__code__icontains=testo_articolo)
        )
    inizio = _offset(offset)
    massimo = _limite(limite, massimo=200)
    elenco = []
    totale = 0
    for livello in livelli:
        if sotto_scorta and not livello.product.is_low_stock:
            continue
        if inizio <= totale < inizio + massimo:
            elenco.append(
                {
                    "articolo": livello.product.code,
                    "nome": livello.product.name,
                    "magazzino": livello.warehouse.name,
                    "quantita": _valore(livello.quantity),
                    "scorta_minima": _valore(livello.product.min_stock),
                }
            )
        totale += 1
    return _pagina(elenco, totale, inizio, massimo)


@_strumento(annotazioni=LETTURA)
def movimenti_magazzino(
    articolo: Annotated[str, Field(description="Nome o codice dell'articolo; vuoto = tutti.")] = "",
    magazzino: Annotated[str, Field(description="Nome o codice del magazzino; vuoto = tutti.")] = "",
    tipo: Annotated[str, Field(description="Tipo di movimento (carico, scarico, rettifica); vuoto = tutti.")] = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Ultimi movimenti di magazzino. Filtri per articolo, magazzino e tipo (carico, scarico, rettifica)."""
    from django.db.models import Q

    from apps.inventory.models import StockMovement

    movimenti = StockMovement.objects.select_related("product", "warehouse").order_by("-created_at")
    testo_articolo = (articolo or "").strip()
    if testo_articolo:
        movimenti = movimenti.filter(
            Q(product__name__icontains=testo_articolo) | Q(product__code__icontains=testo_articolo)
        )
    testo_magazzino = (magazzino or "").strip()
    if testo_magazzino:
        movimenti = movimenti.filter(
            Q(warehouse__name__icontains=testo_magazzino) | Q(warehouse__code__icontains=testo_magazzino)
        )
    codice_tipo = _stato_codice(tipo, StockMovement.TYPE_CHOICES, campo="tipo")
    if codice_tipo:
        movimenti = movimenti.filter(movement_type=codice_tipo)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "data": _valore(m.created_at),
            "articolo": m.product.code,
            "nome": m.product.name,
            "magazzino": m.warehouse.name,
            "tipo": m.get_movement_type_display(),
            "quantita": _valore(m.quantity),
            "costo_unitario": _valore(m.unit_cost),
            "riferimento": m.reference,
            "note": m.note,
        }
        for m in movimenti[inizio : inizio + massimo]
    ]
    return _pagina(elenco, movimenti.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def articoli_sotto_scorta(limite: Limite200 = 50, offset: Offset = 0) -> dict:
    """Articoli la cui giacenza è sotto la scorta minima, con le quantità mancanti."""
    from django.db.models import Sum

    from apps.catalog.models import Product

    articoli = (
        Product.objects.filter(is_stock_tracked=True, min_stock__gt=0, active=True)
        .annotate(giacenza=Sum("stock_levels__quantity"))
        .order_by("name")
    )
    inizio = _offset(offset)
    massimo = _limite(limite, massimo=200)
    elenco = []
    totale = 0
    for a in articoli:
        giacenza = a.giacenza or 0
        if giacenza >= a.min_stock:
            continue
        if inizio <= totale < inizio + massimo:
            elenco.append(
                {
                    "codice": a.code,
                    "nome": a.name,
                    "giacenza": _valore(giacenza),
                    "scorta_minima": _valore(a.min_stock),
                    "mancanti": _valore(a.min_stock - giacenza),
                    "fornitore_abituale": a.main_supplier.name if a.main_supplier_id else "",
                }
            )
        totale += 1
    return _pagina(elenco, totale, inizio, massimo)


@_strumento(annotazioni=LETTURA)
def cerca_articoli(
    testo: Annotated[str, Field(description="Testo da cercare (nome, codice o barcode; almeno 2 caratteri).")],
    limite: Limite50 = 10,
    offset: Offset = 0,
) -> dict:
    """Cerca articoli per nome, codice o codice a barre: prezzi e giacenza totale."""
    from apps.catalog.models import Product
    from apps.catalog.search import filtro_articoli

    testo = (testo or "").strip()
    if len(testo) < 2:
        return {"errore": "Scrivi almeno 2 caratteri."}
    inizio = _offset(offset)
    massimo = _limite(limite)
    articoli = Product.objects.filter(filtro_articoli(testo)).select_related("uom").order_by("name")
    elenco = [
        {
            "codice": a.code,
            "nome": a.name,
            "um": a.uom.code if a.uom_id else "",
            "prezzo_vendita": _valore(a.sale_price),
            "giacenza_totale": _valore(a.total_stock),
        }
        for a in articoli[inizio : inizio + massimo]
    ]
    return _pagina(elenco, articoli.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def giacenza_articolo(codice: Annotated[str, Field(description="Codice esatto dell'articolo.")]) -> dict:
    """Giacenza di un articolo per magazzino e totale (per codice esatto)."""
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


@_strumento(annotazioni=LETTURA)
def dettaglio_articolo(codice: Annotated[str, Field(description="Codice esatto dell'articolo.")]) -> dict:
    """Scheda completa di un articolo per codice: prezzi, IVA, fornitore, giacenze per magazzino,
    componenti se è un kit, varianti e ultimi movimenti."""
    from apps.catalog.models import Product
    from apps.inventory.models import StockLevel, StockMovement

    articolo = (
        Product.objects.select_related("category", "uom", "sale_vat", "purchase_vat", "main_supplier")
        .filter(code=(codice or "").strip())
        .first()
    )
    if articolo is None:
        return {"errore": f"Nessun articolo con codice {codice!r}."}
    livelli = StockLevel.objects.filter(product=articolo).select_related("warehouse").order_by("warehouse__name")
    movimenti = StockMovement.objects.filter(product=articolo).select_related("warehouse")[:5]
    componenti = list(articolo.components.select_related("component")) if articolo.is_kit else []
    varianti = list(articolo.variants.all()) if articolo.parent_id is None else []
    return {
        "codice": articolo.code,
        "nome": articolo.name,
        "categoria": articolo.category.full_name if articolo.category_id else "",
        "um": articolo.uom.code if articolo.uom_id else "",
        "barcode": articolo.barcode,
        "prezzo_vendita": _valore(articolo.sale_price),
        "prezzo_acquisto": _valore(articolo.purchase_price),
        "iva_vendita": str(articolo.sale_vat.rate) if articolo.sale_vat_id else "",
        "iva_acquisto": str(articolo.purchase_vat.rate) if articolo.purchase_vat_id else "",
        "fornitore_abituale": articolo.main_supplier.name if articolo.main_supplier_id else "",
        "giorni_consegna_fornitore": articolo.supplier_lead_days,
        "gestito_a_magazzino": articolo.is_stock_tracked,
        "e_kit": articolo.is_kit,
        "scorta_minima": _valore(articolo.min_stock),
        "sotto_scorta": articolo.is_low_stock,
        "giacenza_totale": _valore(articolo.total_stock),
        "giacenze": [{"magazzino": l.warehouse.name, "quantita": _valore(l.quantity)} for l in livelli],
        "componenti_kit": [
            {"codice": c.component.code, "nome": c.component.name, "quantita": _valore(c.qty)} for c in componenti
        ],
        "varianti": [{"codice": v.code, "nome": v.name, "variante": v.variant_label} for v in varianti],
        "ultimi_movimenti": [
            {
                "data": _valore(m.created_at),
                "tipo": m.get_movement_type_display(),
                "quantita": _valore(m.quantity),
                "magazzino": m.warehouse.name,
                "riferimento": m.reference,
            }
            for m in movimenti
        ],
        "note": articolo.notes or "",
    }


# ================================================================= commesse
def _fatturazione_commessa(job):
    """Situazione della fatturazione di un cantiere (contratto, fatturato, residuo)."""
    from apps.billing import services as billing_services

    riepilogo = billing_services.job_billing_summary(job)
    return {
        "valore_contratto": _valore(riepilogo["contract"]),
        "fatturato": _valore(riepilogo["invoiced"]),
        "acconti": _valore(riepilogo["advances"]),
        "sal": _valore(riepilogo["sal"]),
        "saldo": _valore(riepilogo["balance"]),
        "impegnato": _valore(riepilogo["committed"]),
        "residuo_da_fatturare": _valore(riepilogo["residual"]),
        "prossimo_numero_sal": riepilogo["next_sal_number"],
        "bozze_in_corso": riepilogo["drafts"],
        "documenti": [
            {
                "numero": d.number,
                "data": _valore(d.date),
                "tipo": d.kind_title,
                "stato": d.get_status_display(),
                "imponibile": _valore(d.subtotal),
            }
            for d in riepilogo["documents"][:20]
        ],
    }


@_strumento(annotazioni=LETTURA)
def lista_commesse(
    stato: Annotated[str, Field(description="Stato della commessa (sopralluogo, in preventivazione, confermato, in esecuzione, collaudo, chiuso, annullato); vuoto = tutte.")] = "",
    cliente: Annotated[str, Field(description="Parte del nome del cliente; vuoto = tutte.")] = "",
    solo_aperte: Annotated[bool, Field(description="True per le sole commesse ancora in corso.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca i cantieri/commesse. Stato: sopralluogo, in preventivazione, confermato, in esecuzione,
    collaudo, chiuso, annullato (o vuoto). Con solo_aperte=True solo quelli ancora in corso."""
    from apps.jobs.models import Job

    codice_stato = _stato_codice(stato, Job.STATUS_CHOICES)
    commesse = Job.objects.select_related("customer", "manager").order_by("-created_at")
    if codice_stato:
        commesse = commesse.filter(status=codice_stato)
    if solo_aperte:
        commesse = commesse.filter(status__in=Job.OPEN_STATUSES)
    if (cliente or "").strip():
        commesse = commesse.filter(customer__name__icontains=cliente.strip())
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "codice": j.code,
            "nome": j.name,
            "cliente": j.customer.name,
            "stato": j.get_status_display(),
            "citta": j.city,
            "responsabile": (j.manager.get_full_name() or j.manager.username) if j.manager_id else "",
            "inizio": _valore(j.start_date),
            "fine_prevista": _valore(j.end_date),
        }
        for j in commesse[inizio : inizio + massimo]
    ]
    return _pagina(elenco, commesse.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def dettaglio_commessa(codice: Annotated[str, Field(description="Codice esatto (o nome esatto) della commessa.")]) -> dict:
    """Dettaglio di un cantiere/commessa per codice (o nome esatto): dati, responsabile e riepilogo
    dei documenti collegati."""
    from django.db.models import Count, Sum

    from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice
    from apps.jobs.models import Job
    from apps.purchasing.models import PurchaseOrder
    from apps.sales.models import Quote, SalesOrder

    commessa = Job.objects.select_related("customer", "manager").filter(code=(codice or "").strip()).first()
    if commessa is None:
        # ammette anche il nome esatto del cantiere
        commessa = Job.objects.select_related("customer", "manager").filter(name=(codice or "").strip()).first()
    if commessa is None:
        return {"errore": f"Nessuna commessa con codice o nome {codice!r}."}

    def _conteggio(queryset):
        dati = queryset.aggregate(numero=Count("pk"), totale=Sum("grand_total"))
        return {"numero": dati["numero"] or 0, "totale": _valore(dati["totale"] or 0)}

    return {
        "codice": commessa.code,
        "nome": commessa.name,
        "cliente": commessa.customer.name,
        "stato": commessa.get_status_display(),
        "indirizzo": commessa.full_address,
        "responsabile": (commessa.manager.get_full_name() or commessa.manager.username) if commessa.manager_id else "",
        "inizio": _valore(commessa.start_date),
        "fine_prevista": _valore(commessa.end_date),
        "note": commessa.notes or "",
        "documenti": {
            "preventivi": _conteggio(Quote.objects.filter(job=commessa)),
            "ordini_cliente": _conteggio(SalesOrder.objects.filter(job=commessa)),
            "ddt": {"numero": DeliveryNote.objects.filter(job=commessa).count()},
            "fatture_emesse": _conteggio(SalesInvoice.objects.filter(job=commessa)),
            "ordini_fornitore": _conteggio(PurchaseOrder.objects.filter(job=commessa)),
            "fatture_ricevute": _conteggio(PurchaseInvoice.objects.filter(job=commessa)),
        },
        "fatturazione": _fatturazione_commessa(commessa),
    }


@_strumento(annotazioni=LETTURA)
def manutenzioni_in_scadenza(
    giorni: Annotated[int, Field(ge=0, le=365, description="Orizzonte in giorni da oggi (0-365).")] = 30,
    solo_scadute: Annotated[bool, Field(description="True per le sole manutenzioni già oltre la data prevista.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Manutenzioni programmate attive in scadenza entro N giorni (default 30). Con
    solo_scadute=True solo quelle già oltre la data prevista."""
    from datetime import timedelta

    from apps.jobs.models import MaintenancePlan

    oggi = _oggi()
    try:
        giorni = max(0, int(giorni))
    except (TypeError, ValueError):
        giorni = 30
    piani = MaintenancePlan.objects.filter(active=True).select_related("customer", "job")
    if solo_scadute:
        piani = piani.filter(next_date__lt=oggi)
    else:
        piani = piani.filter(next_date__lte=oggi + timedelta(days=giorni))
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "descrizione": p.name,
            "cliente": p.customer.name,
            "cantiere": p.job.name if p.job_id else "",
            "frequenza": p.get_frequency_display(),
            "prossima_esecuzione": _valore(p.next_date),
            "scaduta": p.is_overdue(),
        }
        for p in piani[inizio : inizio + massimo]
    ]
    return _pagina(elenco, piani.count(), inizio, massimo)


# ====================================================================== CRM
@_strumento(annotazioni=LETTURA)
def lista_lead(
    esito: Annotated[str, Field(description="Esito del lead (in corso, vinta, persa); vuoto = tutti.")] = "",
    fase: Annotated[str, Field(description="Parte del nome della fase; vuoto = tutte.")] = "",
    solo_azione_in_ritardo: Annotated[bool, Field(description="True per i soli lead con la prossima azione in ritardo.")] = False,
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Elenca i lead commerciali. Esito: in corso, vinta, persa (o vuoto). Filtri per fase (parte del
    nome) e per i soli con la prossima azione in ritardo."""
    from apps.leads.models import Lead, LeadStage

    codice_esito = _stato_codice(esito, LeadStage.KIND_CHOICES, campo="esito")
    lead = Lead.objects.select_related("stage", "contact", "owner").order_by("next_action", "-created_at")
    if codice_esito:
        lead = lead.filter(stage__kind=codice_esito)
    if (fase or "").strip():
        lead = lead.filter(stage__name__icontains=fase.strip())
    oggi = _oggi()
    if solo_azione_in_ritardo:
        lead = lead.filter(next_action__lt=oggi)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "nome": l.name,
            "fase": l.stage.name,
            "esito": l.stage.get_kind_display(),
            "contatto": l.contact.name if l.contact_id else "",
            "citta": l.city,
            "valore_stimato": _valore(l.estimated_value),
            "prossima_azione": _valore(l.next_action),
            "in_ritardo": bool(l.next_action and l.next_action < oggi),
            "responsabile": l.owner.username if l.owner_id else "",
        }
        for l in lead[inizio : inizio + massimo]
    ]
    return _pagina(elenco, lead.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def riepilogo_pipeline() -> dict:
    """Riepilogo della pipeline lead: numero e valore stimato per ogni fase."""
    from django.db.models import Count, Sum

    from apps.leads.models import Lead, LeadStage

    oggi = _oggi()
    fasi = LeadStage.objects.all().order_by("order", "name")
    dati = {
        r["stage_id"]: r
        for r in Lead.objects.values("stage_id").annotate(numero=Count("pk"), valore=Sum("estimated_value"))
    }
    elenco = []
    for fase in fasi:
        r = dati.get(fase.pk, {"numero": 0, "valore": 0})
        elenco.append(
            {
                "fase": fase.name,
                "esito": fase.get_kind_display(),
                "numero_lead": r["numero"],
                "valore_stimato": _valore(r["valore"] or 0),
            }
        )
    in_ritardo = Lead.objects.filter(stage__kind=LeadStage.KIND_OPEN, next_action__lt=oggi).count()
    return {"fasi": elenco, "lead_con_azione_in_ritardo": in_ritardo}


# ================================================================= personale
@_strumento(annotazioni=LETTURA)
def lista_dipendenti(
    solo_attivi: Annotated[bool, Field(description="True per i soli dipendenti attivi.")] = True,
    limite: Limite50 = 50,
    offset: Offset = 0,
) -> dict:
    """Elenca i dipendenti con mansione, contatti e costo orario."""
    from apps.hr.models import Employee

    dipendenti = Employee.objects.all().order_by("last_name", "first_name")
    if solo_attivi:
        dipendenti = dipendenti.filter(active=True)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "codice": e.code,
            "nome": e.full_name,
            "mansione": e.qualification,
            "email": e.email,
            "telefono": e.phone,
            "assunto_il": _valore(e.hired_on),
            "costo_orario": _valore(e.hourly_cost),
            "attivo": e.active,
        }
        for e in dipendenti[inizio : inizio + massimo]
    ]
    return _pagina(elenco, dipendenti.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def lista_collaboratori(
    solo_attivi: Annotated[bool, Field(description="True per i soli collaboratori attivi.")] = True,
    limite: Limite50 = 50,
    offset: Offset = 0,
) -> dict:
    """Elenca i collaboratori esterni con specializzazione e tariffa oraria."""
    from apps.hr.models import Collaborator

    collaboratori = Collaborator.objects.all().order_by("name")
    if solo_attivi:
        collaboratori = collaboratori.filter(active=True)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "codice": c.code,
            "nome": c.name,
            "azienda": c.company,
            "specializzazione": c.specialization,
            "email": c.email,
            "telefono": c.phone,
            "tariffa_oraria": _valore(c.hourly_rate),
            "attivo": c.active,
        }
        for c in collaboratori[inizio : inizio + massimo]
    ]
    return _pagina(elenco, collaboratori.count(), inizio, massimo)


# ============================================================ ore e assenze
def _filtro_dipendente(testo):
    """Filtro ORM su TimeEntry/LeaveRequest: codice, nome o cognome del dipendente."""
    from django.db.models import Q

    filtro = Q(employee__code__icontains=(testo or "").strip())
    for parola in (testo or "").split():
        filtro |= Q(employee__first_name__icontains=parola) | Q(employee__last_name__icontains=parola)
    return filtro


@_strumento(annotazioni=LETTURA)
def lista_ore(
    dipendente: Annotated[str, Field(description="Codice o nome del dipendente; vuoto = tutti.")] = "",
    cantiere: Annotated[str, Field(description="Codice o nome del cantiere; vuoto = tutti.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    tipo: Annotated[str, Field(description="Tipo di ore (ordinario, straordinario, trasferta); vuoto = tutti.")] = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Ore registrate dai dipendenti, più recenti prima. Filtri per dipendente (codice o nome),
    cantiere (codice o nome), tipo (ordinario, straordinario, trasferta) e intervallo date."""
    from django.db.models import Q

    from apps.hr.models import TimeEntry

    da, a = _intervallo(da_data, a_data)
    voci = TimeEntry.objects.select_related("employee", "job").order_by("-date", "-pk")
    if (dipendente or "").strip():
        voci = voci.filter(_filtro_dipendente(dipendente))
    if (cantiere or "").strip():
        testo = cantiere.strip()
        voci = voci.filter(Q(job__code__iexact=testo) | Q(job__name__icontains=testo))
    codice_tipo = _stato_codice(tipo, TimeEntry.KIND_CHOICES, campo="tipo")
    if codice_tipo:
        voci = voci.filter(kind=codice_tipo)
    if da:
        voci = voci.filter(date__gte=da)
    if a:
        voci = voci.filter(date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "data": _valore(v.date),
            "dipendente": v.employee.full_name,
            "codice": v.employee.code,
            "ore": _valore(v.hours),
            "tipo": v.get_kind_display(),
            "cantiere": v.job.name if v.job_id else "",
            "descrizione": v.description,
            "addebitabile": v.billable,
            "costo": _valore(v.cost) if v.cost is not None else "",
        }
        for v in voci[inizio : inizio + massimo]
    ]
    return _pagina(elenco, voci.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def riepilogo_ore(da_data: DataDa = "", a_data: DataA = "") -> dict:
    """Ore e costo per dipendente nel periodo (default: mese corrente), con i totali per tipo."""
    from django.db.models import Count, Q, Sum

    from apps.hr.models import Employee, TimeEntry

    oggi = _oggi()
    da, a = _intervallo(da_data, a_data)
    if da is None and a is None:
        da, a = oggi.replace(day=1), oggi
    filtri = {}
    if da:
        filtri["date__gte"] = da
    if a:
        filtri["date__lte"] = a
    costi = {e.pk: e.hourly_cost for e in Employee.objects.all()}
    righe = (
        TimeEntry.objects.filter(**filtri)
        .values("employee_id", "employee__code", "employee__first_name", "employee__last_name")
        .annotate(
            ore=Sum("hours"),
            registrazioni=Count("pk"),
            ordinarie=Sum("hours", filter=Q(kind=TimeEntry.KIND_ORDINARY)),
            straordinarie=Sum("hours", filter=Q(kind=TimeEntry.KIND_OVERTIME)),
            trasferte=Sum("hours", filter=Q(kind=TimeEntry.KIND_TRAVEL)),
        )
        .order_by("employee__last_name", "employee__first_name")
    )
    elenco = []
    totale_ore = 0
    totale_costo = 0
    for r in righe:
        ore = r["ore"] or 0
        costo_orario = costi.get(r["employee_id"])
        costo = (costo_orario or 0) * ore
        totale_ore += ore
        totale_costo += costo
        elenco.append(
            {
                "dipendente": f"{r['employee__last_name']} {r['employee__first_name']}".strip(),
                "codice": r["employee__code"],
                "ore": _valore(ore),
                "ordinarie": _valore(r["ordinarie"] or 0),
                "straordinarie": _valore(r["straordinarie"] or 0),
                "trasferte": _valore(r["trasferte"] or 0),
                "registrazioni": r["registrazioni"],
                "costo": _valore(costo) if costo_orario is not None else "",
            }
        )
    return {
        "periodo": {"da": _valore(da) if da else "", "a": _valore(a) if a else ""},
        "dipendenti": elenco,
        "totale_ore": _valore(totale_ore),
        "totale_costo": _valore(totale_costo),
    }


@_strumento(annotazioni=LETTURA)
def lista_assenze(
    dipendente: Annotated[str, Field(description="Codice o nome del dipendente; vuoto = tutti.")] = "",
    stato: Annotated[str, Field(description="Stato dell'assenza (richiesta, approvata, rifiutata, annullata); vuoto = tutte.")] = "",
    da_data: DataDa = "",
    a_data: DataA = "",
    limite: Limite50 = 20,
    offset: Offset = 0,
) -> dict:
    """Ferie, permessi e altre assenze dei dipendenti, dalla più recente. Filtri per dipendente,
    stato (richiesta, approvata, rifiutata, annullata) e intervallo date (assenze che lo toccano)."""
    from apps.hr.models import LeaveRequest

    da, a = _intervallo(da_data, a_data)
    assenze = LeaveRequest.objects.select_related("employee").order_by("-start_date", "-pk")
    if (dipendente or "").strip():
        assenze = assenze.filter(_filtro_dipendente(dipendente))
    codice_stato = _stato_codice(stato, LeaveRequest.STATUS_CHOICES)
    if codice_stato:
        assenze = assenze.filter(status=codice_stato)
    if da:
        assenze = assenze.filter(end_date__gte=da)
    if a:
        assenze = assenze.filter(start_date__lte=a)
    inizio = _offset(offset)
    massimo = _limite(limite)
    elenco = [
        {
            "id": a_.pk,
            "dipendente": a_.employee.full_name,
            "codice": a_.employee.code,
            "tipo": a_.get_kind_display(),
            "dal": _valore(a_.start_date),
            "al": _valore(a_.end_date),
            "durata": a_.duration_label,
            "giorni": a_.days,
            "ore": _valore(a_.hours) if a_.hours is not None else "",
            "stato": a_.get_status_display(),
            "motivo": a_.reason,
        }
        for a_ in assenze[inizio : inizio + massimo]
    ]
    return _pagina(elenco, assenze.count(), inizio, massimo)


@_strumento(annotazioni=LETTURA)
def scheda_dipendente(codice: Annotated[str, Field(description="Codice esatto del dipendente.")]) -> dict:
    """Scheda di un dipendente per codice: anagrafica, saldi ferie/permessi dell'anno,
    ore dell'anno per tipo e ultime assenze."""
    from datetime import date

    from django.utils import timezone

    from apps.hr.models import Employee, TimeEntry

    dipendente = Employee.objects.select_related("user").filter(code=(codice or "").strip()).first()
    if dipendente is None:
        return {"errore": f"Nessun dipendente con codice {codice!r}."}
    anno = timezone.localdate().year
    inizio, fine = date(anno, 1, 1), date(anno, 12, 31)
    assenze = dipendente.leave_requests.order_by("-start_date", "-pk")[:5]
    return {
        "codice": dipendente.code,
        "nome": dipendente.full_name,
        "mansione": dipendente.qualification,
        "email": dipendente.email,
        "telefono": dipendente.phone,
        "utente_collegato": dipendente.user.username if dipendente.user_id else "",
        "assunto_il": _valore(dipendente.hired_on),
        "cessato_il": _valore(dipendente.terminated_on),
        "attivo": dipendente.active,
        "costo_orario": _valore(dipendente.hourly_cost) if dipendente.hourly_cost is not None else "",
        "ore_settimanali": _valore(dipendente.contract_weekly_hours),
        "saldi": {
            "anno": anno,
            "ferie_residue": _valore(dipendente.holiday_balance(anno)),
            "permessi_residui_ore": _valore(dipendente.rol_balance(anno)),
            "ore_anno": {
                etichetta: _valore(dipendente.hours_between(inizio, fine, kind=codice_tipo))
                for codice_tipo, etichetta in TimeEntry.KIND_CHOICES
            },
        },
        "ultime_assenze": [
            {
                "tipo": a.get_kind_display(),
                "dal": _valore(a.start_date),
                "al": _valore(a.end_date),
                "durata": a.duration_label,
                "stato": a.get_status_display(),
            }
            for a in assenze
        ],
    }
