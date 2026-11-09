"""Servizi di acquisti: variazioni listino e ricezione merci."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement

from .models import PriceListAdjustment, PurchaseOrder, PurchaseOrderLine, round4


def apply_pricelist_adjustment(pricelist, percent, user=None):
    """Applica una variazione percentuale a tutte le voci del listino.

    ``percent`` positivo aumenta i prezzi, negativo li diminuisce.
    """
    percent = Decimal(str(percent))
    if percent == 0:
        raise ValidationError("La variazione percentuale non può essere zero.")
    if percent <= -100:
        raise ValidationError("La variazione non può essere inferiore o uguale a -100%.")

    factor = 1 + percent / 100
    items = list(pricelist.items.select_related("product"))
    if not items:
        raise ValidationError("Il listino non contiene articoli da aggiornare.")

    with transaction.atomic():
        for item in items:
            item.price = round4(Decimal(item.price or 0) * factor)
            item.save(update_fields=["price", "updated_at"])
        adjustment = PriceListAdjustment.objects.create(
            pricelist=pricelist,
            percent=percent,
            items_count=len(items),
            applied_by=user,
        )
    return adjustment


# Margine oltre il netto atteso entro cui un prezzo di listino si considera
# «già scontato» (arrotondamenti, piccoli aumenti di listino).
TOLLERANZA_GIA_NETTO = Decimal("1.10")


def voci_gia_nette(pricelist, percentuale):
    """Voci del listino il cui prezzo sembra già il netto d'acquisto.

    Lo sconto del fornitore va applicato al prezzo di listino lordo (il prezzo
    al pubblico, che di norma è anche il prezzo di vendita dell'articolo). Se
    il prezzo della voce è già vicino a «prezzo di vendita meno sconto», lo
    sconto è già stato applicato: farlo di nuovo abbatte il costo. È successo
    con un listino importato da Odoo, dove il prezzo era già quello netto: i
    costi sono finiti al 10% del listino invece del 32% e i margini dei
    preventivi sono risultati gonfiati.

    Restituisce ``(voci_sospette, voci_controllate)``.
    """
    fattore = 1 - Decimal(percentuale) / 100
    if fattore >= 1:
        return [], 0
    sospette = []
    controllate = 0
    for voce in pricelist.items.select_related("product"):
        vendita = Decimal(voce.product.sale_price or 0)
        prezzo = Decimal(voce.price or 0)
        if vendita <= 0 or prezzo <= 0:
            continue
        controllate += 1
        if prezzo <= vendita * fattore * TOLLERANZA_GIA_NETTO:
            sospette.append(voce)
    return sospette, controllate


def applica_sconto_listino(pricelist, percentuale, forza=False):
    """Imposta lo sconto fornitore su tutte le voci e ricalcola i costi d'acquisto.

    Il prezzo di acquisto di ogni articolo diventa «prezzo della voce meno lo
    sconto». Se più della metà delle voci ha già un prezzo netto (vedi
    ``voci_gia_nette``) si rifiuta, a meno di ``forza=True``: lo sconto
    verrebbe applicato due volte.

    Restituisce ``(voci_del_listino, articoli_aggiornati)``.
    """
    from apps.catalog.models import Product

    percentuale = Decimal(str(percentuale))
    if percentuale < 0 or percentuale > 100:
        raise ValidationError("Lo sconto deve essere fra 0 e 100.")
    if percentuale > 0 and not forza:
        sospette, controllate = voci_gia_nette(pricelist, percentuale)
        if controllate and len(sospette) * 2 > controllate:
            raise ValidationError(
                f"Sconto non applicato: {len(sospette)} voci su {controllate} hanno già un prezzo vicino al "
                f"netto (prezzo di vendita meno {percentuale}%). Sembra che il listino contenga già i prezzi "
                "scontati: applicando lo sconto i costi d'acquisto verrebbero scontati due volte. "
                "Inserisci nel listino i prezzi lordi (di listino) e poi applica lo sconto."
            )

    da_salvare = []
    with transaction.atomic():
        for voce in pricelist.items.select_related("product"):
            prodotto = voce.product
            prezzo = round4(Decimal(voce.price or 0) * (1 - percentuale / 100))
            if prodotto.purchase_price != prezzo:
                prodotto.purchase_price = prezzo
                da_salvare.append(prodotto)
        pricelist.items.update(discount_pct=percentuale)
        Product.objects.bulk_update(da_salvare, ["purchase_price"], batch_size=500)
    return pricelist.items.count(), len(da_salvare)


def receive_purchase_order(po, quantities, user=None, warehouse=None, ddt=""):
    """Registra la ricezione merce per le righe indicate.

    ``quantities``: dict {line_id: qty}; ``ddt`` è il numero del DDT del
    fornitore (facoltativo, resta scritto sull'ordine e nei movimenti di
    magazzino). Restituisce (righe_ricevute, errori).
    """
    received_lines = []
    errors = []
    ddt = (ddt or "").strip()[:50]
    if ddt and ddt != po.supplier_ddt:
        po.supplier_ddt = ddt
    nota = f"Ricezione {po.number}"
    if ddt:
        nota += f" – DDT {ddt}"
    for line in po.lines.select_related("product"):
        raw = quantities.get(str(line.pk))
        if raw in (None, ""):
            continue
        try:
            qty = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            errors.append(f"Quantità non valida per «{line.description}».")
            continue
        if qty <= 0:
            continue
        if qty > line.qty_remaining:
            errors.append(f"«{line.description}»: ricevuti {qty} ma ne mancano solo {line.qty_remaining}.")
            continue

        with transaction.atomic():
            # La riga si aggiorna solo se la quantità ricevuta è ancora quella
            # letta (e controllata) qui sopra: due invii dello stesso modulo
            # (doppio clic, due magazzinieri) non caricano due volte la merce.
            # Prima la seconda richiesta riscriveva il valore senza vedere la
            # prima. Il nuovo valore si calcola in Decimal, esatto anche su SQLite.
            presa = PurchaseOrderLine.objects.filter(pk=line.pk, qty_received=line.qty_received).update(
                qty_received=line.qty_received + qty
            )
            if not presa:
                errors.append(f"«{line.description}»: la merce risulta già ricevuta nel frattempo, ricarica la pagina.")
                continue
            if line.product is not None and line.product.is_stock_tracked:
                register_movement(
                    product=line.product,
                    warehouse=warehouse,
                    delta=qty,
                    movement_type=StockMovement.TYPE_LOAD,
                    user=user,
                    reference=po.number,
                    note=nota,
                    unit_cost=line.unit_cost,
                )
        line.refresh_from_db(fields=["qty_received"])
        received_lines.append(line)

    campi = []
    if received_lines:
        if po.all_received:
            po.status = PurchaseOrder.STATUS_RECEIVED
        else:
            po.status = PurchaseOrder.STATUS_PARTIAL
        campi.append("status")
    if ddt:
        campi.append("supplier_ddt")
    if campi:
        po.save(update_fields=campi)

    return received_lines, errors


def cancel_purchase_order(po, user=None):
    if po.status == PurchaseOrder.STATUS_RECEIVED:
        raise ValidationError("Un ordine già ricevuto non può essere annullato.")
    if po.lines.filter(qty_received__gt=0).exists():
        raise ValidationError("Alcune righe sono già state ricevute: impossibile annullare.")
    po.status = PurchaseOrder.STATUS_CANCELLED
    po.save(update_fields=["status"])
    return po
