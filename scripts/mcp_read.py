"""Strumenti MCP del gestionale in sola lettura.

Coprono l'intero perimetro del gestionale: anagrafiche, preventivi, ordini
cliente, DDT, fatture emesse e ricevute, ordini fornitore, magazzino,
catalogo, commesse, lead, personale e impostazioni. Tutte le funzioni leggono
soltanto il database.
"""
from mcp_common import (
    _intervallo,
    _limite,
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
@_strumento
def cerca_clienti(testo: str, limite: int = 10) -> list:
    """Cerca clienti e fornitori per nome, codice, città, email o P.IVA."""
    from django.db.models import Q

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


@_strumento
def scheda_cliente(codice: str) -> dict:
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
                **_riga(f, "number", "date", "due_date", "status", "subtotal", "grand_total"),
                "scaduta": bool(f.due_date and f.due_date < oggi),
            }
            for f in fatture
        ],
    }


@_strumento
def dati_azienda() -> dict:
    """Dati anagrafici dell'azienda (nome, P.IVA, indirizzo, contatti, IBAN)."""
    from apps.core.models import CompanySettings

    azienda = CompanySettings.load()
    return _riga(
        azienda, "name", "vat_number", "tax_code", "pec", "fiscal_regime", "address",
        "zip_code", "city", "province", "country", "email", "phone", "website", "iban",
    )


@_strumento
def lista_termini_pagamento() -> list:
    """Elenca le condizioni di pagamento (nome, giorni, fine mese)."""
    from apps.core.models import PaymentTerm

    return [
        {"nome": t.name, "giorni": t.days, "fine_mese": t.end_of_month, "note": t.notes}
        for t in PaymentTerm.objects.order_by("days", "name")
    ]


# ================================================================ preventivi
@_strumento
def lista_preventivi(stato: str = "", cliente: str = "", da_data: str = "", a_data: str = "", limite: int = 20) -> list:
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
    return [
        {
            "numero": q.number,
            "data": _valore(q.date),
            "valido_fino_al": _valore(q.valid_until),
            "cliente": q.customer.name,
            "stato": q.get_status_display(),
            "imponibile": _valore(q.subtotal),
            "totale": _valore(q.grand_total),
        }
        for q in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_preventivo(numero: str) -> dict:
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


@_strumento
def preventivi_in_scadenza(giorni: int = 7, limite: int = 20) -> dict:
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

    def _elenco(queryset):
        return [
            {
                "numero": q.number,
                "data": _valore(q.date),
                "valido_fino_al": _valore(q.valid_until),
                "cliente": q.customer.name,
                "stato": q.get_status_display(),
                "totale": _valore(q.grand_total),
            }
            for q in queryset.order_by("valid_until")[: _limite(limite)]
        ]

    scaduti = base.filter(valid_until__lt=oggi)
    in_scadenza = base.filter(valid_until__gte=oggi, valid_until__lte=oggi + timedelta(days=giorni))
    return {
        "entro_il": _valore(oggi + timedelta(days=giorni)),
        "preventivi_scaduti": {"numero": scaduti.count(), "elenco": _elenco(scaduti)},
        "preventivi_in_scadenza": {"numero": in_scadenza.count(), "elenco": _elenco(in_scadenza)},
    }


# ===================================================== ordini cliente (vendite)
@_strumento
def lista_ordini(stato: str = "", cliente: str = "", da_data: str = "", a_data: str = "", limite: int = 20) -> list:
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
    return [
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
        for o in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_ordine(numero: str) -> dict:
    """Dettaglio di un ordine cliente per numero: testata, righe con quantità consegnate/residue,
    DDT e fatture collegate, eventuale provvvigione."""
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


@_strumento
def ordini_da_consegnare(solo_in_ritardo: bool = False, limite: int = 20) -> dict:
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
    elenco = []
    for o in ordini[: _limite(limite)]:
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
    return {
        "totale_ordini": ordini.count(),
        "filtro": "solo in ritardo" if solo_in_ritardo else "tutti quelli confermati non consegnati",
        "ordini": elenco,
    }


# ======================================================================= DDT
@_strumento
def lista_ddt(stato: str = "", cliente: str = "", da_data: str = "", a_data: str = "", limite: int = 20) -> list:
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
    return [
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
        for d in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_ddt(numero: str) -> dict:
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


@_strumento
def ddt_da_fatturare(limite: int = 20) -> list:
    """DDT emessi e non ancora fatturati, in ordine di data."""
    from apps.billing.models import DeliveryNote

    ddt = (
        DeliveryNote.objects.filter(status=DeliveryNote.STATUS_ISSUED, invoiced=False)
        .select_related("customer", "source_order")
        .order_by("date")
    )
    return [
        {
            "numero": d.number,
            "data": _valore(d.date),
            "cliente": d.customer.name,
            "ordine": d.source_order.number if d.source_order_id else "",
            "totale_quantita": _valore(d.total_qty),
        }
        for d in ddt[: _limite(limite)]
    ]


# ========================================================== fatture emesse
@_strumento
def fatture_da_incassare(solo_scadute: bool = False, limite: int = 20) -> list:
    """Fatture emesse non pagate (inviate o emesse), con flag scadute."""
    from apps.billing.models import SalesInvoice

    oggi = _oggi()
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


@_strumento
def lista_fatture(
    stato: str = "", cliente: str = "", da_data: str = "", a_data: str = "", solo_scadute: bool = False, limite: int = 20
) -> list:
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
    return [
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
        for f in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_fattura(numero: str) -> dict:
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


@_strumento
def fatturato_periodo(da_data: str = "", a_data: str = "") -> dict:
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


# ===================================================== fatture ricevute (acquisti)
@_strumento
def lista_fatture_fornitori(
    stato: str = "", fornitore: str = "", da_data: str = "", a_data: str = "", solo_scadute: bool = False, limite: int = 20
) -> list:
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
    return [
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
        for f in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_fattura_fornitore(numero: str) -> dict:
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


@_strumento
def fatture_fornitori_da_pagare(solo_scadute: bool = False, limite: int = 20) -> list:
    """Fatture ricevute registrate e non ancora pagate, con flag scadute."""
    from apps.billing.models import PurchaseInvoice

    oggi = _oggi()
    fatture = PurchaseInvoice.objects.filter(status=PurchaseInvoice.STATUS_REGISTERED).select_related("supplier")
    if solo_scadute:
        fatture = fatture.filter(due_date__lt=oggi)
    fatture = fatture.order_by("due_date")[: _limite(limite)]
    return [
        {
            "numero": f.number,
            "documento_fornitore": f.supplier_reference,
            "data": _valore(f.date),
            "scadenza": _valore(f.due_date),
            "fornitore": f.supplier.name,
            "scaduta": bool(f.due_date and f.due_date < oggi),
            "totale": _valore(f.grand_total),
        }
        for f in fatture
    ]


# =============================================================== scadenzario
@_strumento
def scadenzario(giorni: int = 30, limite: int = 20) -> dict:
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

    def _elenco(queryset, fornitore=False):
        elenco = []
        for f in queryset.order_by("due_date")[: _limite(limite)]:
            elenco.append(
                {
                    "numero": f.number,
                    "contatto": f.supplier.name if fornitore else f.customer.name,
                    "scadenza": _valore(f.due_date),
                    "totale": _valore(f.grand_total),
                    "scaduta": bool(f.due_date and f.due_date < oggi),
                }
            )
        return elenco

    def _sommario(queryset):
        dati = queryset.aggregate(numero=Count("pk"), totale=Sum("grand_total"))
        return {"numero": dati["numero"] or 0, "totale": _valore(dati["totale"] or 0)}

    da_incassare = crediti.filter(due_date__gte=oggi, due_date__lte=fino)
    incassare_scaduti = crediti.filter(due_date__lt=oggi)
    da_pagare = debiti.filter(due_date__gte=oggi, due_date__lte=fino)
    pagare_scaduti = debiti.filter(due_date__lt=oggi)
    return {
        "entro_il": _valore(fino),
        "da_incassare": {**_sommario(da_incassare), "elenco": _elenco(da_incassare)},
        "da_pagare": {**_sommario(da_pagare), "elenco": _elenco(da_pagare, fornitore=True)},
        "scaduti_da_incassare": {**_sommario(incassare_scaduti), "elenco": _elenco(incassare_scaduti)},
        "scaduti_da_pagare": {**_sommario(pagare_scaduti), "elenco": _elenco(pagare_scaduti, fornitore=True)},
    }


# ========================================================== ordini fornitore
@_strumento
def lista_ordini_fornitore(
    stato: str = "", fornitore: str = "", da_data: str = "", a_data: str = "", limite: int = 20
) -> list:
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
    return [
        {
            "numero": o.number,
            "data": _valore(o.date),
            "consegna_prevista": _valore(o.expected_date),
            "fornitore": o.supplier.name,
            "stato": o.get_status_display(),
            "totale": _valore(o.grand_total),
            "in_ritardo": bool(o.expected_date and o.expected_date < oggi and not o.all_received),
        }
        for o in righe[: _limite(limite)]
    ]


@_strumento
def dettaglio_ordine_fornitore(numero: str) -> dict:
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


@_strumento
def ordini_fornitore_da_ricevere(solo_in_ritardo: bool = False, limite: int = 20) -> dict:
    """Ordini fornitore ancora da ricevere (inviati, confermati o parzialmente ricevuti), con le
    quantità residue. Con solo_in_ritardo=True solo quelli oltre la consegna prevista."""
    from apps.purchasing.models import PurchaseOrder

    oggi = _oggi()
    ordini = PurchaseOrder.objects.filter(
        status__in=[
            PurchaseOrder.STATUS_SENT,
            PurchaseOrder.STATUS_CONFIRMED,
            PurchaseOrder.STATUS_PARTIAL,
        ]
    ).select_related("supplier")
    if solo_in_ritardo:
        ordini = ordini.filter(expected_date__lt=oggi)
    ordini = ordini.order_by("expected_date", "date")
    elenco = []
    for o in ordini[: _limite(limite)]:
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
    return {"totale_ordini": ordini.count(), "ordini": elenco}


@_strumento
def lista_listini(fornitore: str = "", solo_attivi: bool = True, limite: int = 20) -> list:
    """Elenca i listini prezzi dei fornitori, con validità e numero di voci."""
    from django.db.models import Count

    from apps.purchasing.models import SupplierPriceList

    listini = SupplierPriceList.objects.select_related("supplier").annotate(voci=Count("items"))
    if (fornitore or "").strip():
        listini = listini.filter(supplier__name__icontains=fornitore.strip())
    if solo_attivi:
        listini = listini.filter(is_active=True)
    return [
        {
            "nome": l.name,
            "fornitore": l.supplier.name,
            "valido_dal": _valore(l.valid_from),
            "valido_fino_al": _valore(l.valid_to),
            "attivo": l.is_active,
            "corrente": l.is_current,
            "voci": l.voci,
        }
        for l in listini[: _limite(limite)]
    ]


# ================================================================= magazzino
@_strumento
def lista_magazzini(solo_attivi: bool = True) -> list:
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
    return [
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


@_strumento
def giacenze(magazzino: str = "", articolo: str = "", sotto_scorta: bool = False, limite: int = 50) -> list:
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
    massimo = _limite(limite, massimo=200)
    elenco = []
    for livello in livelli:
        if sotto_scorta and not livello.product.is_low_stock:
            continue
        elenco.append(
            {
                "articolo": livello.product.code,
                "nome": livello.product.name,
                "magazzino": livello.warehouse.name,
                "quantita": _valore(livello.quantity),
                "scorta_minima": _valore(livello.product.min_stock),
            }
        )
        if len(elenco) >= massimo:
            break
    return elenco


@_strumento
def movimenti_magazzino(articolo: str = "", magazzino: str = "", tipo: str = "", limite: int = 20) -> list:
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
    return [
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
        for m in movimenti[: _limite(limite)]
    ]


@_strumento
def articoli_sotto_scorta(limite: int = 50) -> list:
    """Articoli la cui giacenza è sotto la scorta minima, con le quantità mancanti."""
    from django.db.models import Sum

    from apps.catalog.models import Product

    articoli = (
        Product.objects.filter(is_stock_tracked=True, min_stock__gt=0, active=True)
        .annotate(giacenza=Sum("stock_levels__quantity"))
        .order_by("name")
    )
    massimo = _limite(limite, massimo=200)
    elenco = []
    for a in articoli:
        giacenza = a.giacenza or 0
        if giacenza >= a.min_stock:
            continue
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
        if len(elenco) >= massimo:
            break
    return elenco


@_strumento
def cerca_articoli(testo: str, limite: int = 10) -> list:
    """Cerca articoli per nome, codice o codice a barre: prezzi e giacenza totale."""
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


@_strumento
def giacenza_articolo(codice: str) -> dict:
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


@_strumento
def dettaglio_articolo(codice: str) -> dict:
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
@_strumento
def lista_commesse(stato: str = "", cliente: str = "", solo_aperte: bool = False, limite: int = 20) -> list:
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
    return [
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
        for j in commesse[: _limite(limite)]
    ]


@_strumento
def dettaglio_commessa(codice: str) -> dict:
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
    }


@_strumento
def manutenzioni_in_scadenza(giorni: int = 30, solo_scadute: bool = False, limite: int = 20) -> list:
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
    return [
        {
            "descrizione": p.name,
            "cliente": p.customer.name,
            "cantiere": p.job.name if p.job_id else "",
            "frequenza": p.get_frequency_display(),
            "prossima_esecuzione": _valore(p.next_date),
            "scaduta": p.is_overdue(),
        }
        for p in piani[: _limite(limite)]
    ]


# ====================================================================== CRM
@_strumento
def lista_lead(esito: str = "", fase: str = "", solo_azione_in_ritardo: bool = False, limite: int = 20) -> list:
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
    return [
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
        for l in lead[: _limite(limite)]
    ]


@_strumento
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
@_strumento
def lista_dipendenti(solo_attivi: bool = True, limite: int = 50) -> list:
    """Elenca i dipendenti con mansione, contatti e costo orario."""
    from apps.hr.models import Employee

    dipendenti = Employee.objects.all().order_by("last_name", "first_name")
    if solo_attivi:
        dipendenti = dipendenti.filter(active=True)
    return [
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
        for e in dipendenti[: _limite(limite)]
    ]


@_strumento
def lista_collaboratori(solo_attivi: bool = True, limite: int = 50) -> list:
    """Elenca i collaboratori esterni con specializzazione e tariffa oraria."""
    from apps.hr.models import Collaborator

    collaboratori = Collaborator.objects.all().order_by("name")
    if solo_attivi:
        collaboratori = collaboratori.filter(active=True)
    return [
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
        for c in collaboratori[: _limite(limite)]
    ]
