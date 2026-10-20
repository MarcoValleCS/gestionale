"""Strumenti MCP del gestionale per le scritture.

Creano e aggiornano i documenti riusando la logica di business già presente in
``apps/*/services.py`` (conversioni, conferme, consegne, fatturazioni,
movimenti di magazzino): gli strumenti non reimplementano regole, si limitano
a tradurre la richiesta in linguaggio naturale nelle chiamate ai servizi. Ogni
scrittura è esplicita: non ci sono cancellazioni, quelle restano nell'interfaccia
del gestionale.
"""
from typing import Annotated, Optional

from pydantic import Field

from mcp_common import (
    CREAZIONE,
    MODIFICA,
    MODIFICA_RIPETIBILE,
    _data,
    _dec,
    _stato_codice,
    _strumento,
    _valore,
    utente_sistema,
)


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


def _risolvi_listino(testo, fornitore=""):
    """Listino fornitore per nome esatto o, se univoco, per parte del nome."""
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


def _risolvi_dipendente(testo):
    """Dipendente per codice esatto o, se univoco, per nome/cognome."""
    from django.db.models import Q

    from apps.hr.models import Employee

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare il dipendente (codice o nome).")
    dipendente = Employee.objects.filter(code__iexact=testo).first()
    if dipendente is not None:
        return dipendente
    filtro = Q()
    for parola in testo.split():
        filtro &= Q(first_name__icontains=parola) | Q(last_name__icontains=parola)
    trovati = list(Employee.objects.filter(filtro)[:5])
    if not trovati:
        raise ValueError(f"Nessun dipendente che corrisponde a {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(f"{e.code} {e.full_name}" for e in trovati)
        raise ValueError(f"Più dipendenti trovati per {testo!r}: {elenco}. Usa il codice.")
    return trovati[0]


def _risolvi_collaboratore(testo):
    """Collaboratore per codice esatto o, se univoco, per nome."""
    from apps.hr.models import Collaborator

    testo = (testo or "").strip()
    if not testo:
        raise ValueError("Specificare il collaboratore (codice o nome).")
    collaboratore = Collaborator.objects.filter(code__iexact=testo).first()
    if collaboratore is not None:
        return collaboratore
    trovati = list(Collaborator.objects.filter(name__icontains=testo)[:5])
    if not trovati:
        raise ValueError(f"Nessun collaboratore che contiene {testo!r}.")
    if len(trovati) > 1:
        elenco = ", ".join(f"{c.code} {c.name}" for c in trovati)
        raise ValueError(f"Più collaboratori trovati per {testo!r}: {elenco}. Usa il codice.")
    return trovati[0]


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


def _espandi_kit(documento, fk_field):
    """Aggiunge le righe dei componenti dei kit rimasti chiusi.

    Come nell'interfaccia: il kit è una riga sola che, alla consegna, deve
    scaricare i pezzi e non il kit (che a magazzino non esiste).
    """
    from apps.sales import services as sales_services

    return sales_services.espandi_kit(documento, fk_field)


def _riepilogo(doc):
    return {"numero": doc.number, "data": _valore(doc.date), "totale": _valore(doc.grand_total)}


def _avvisi(errori):
    """Normalizza i messaggi di errore dei servizi (ValidationError → testo pulito)."""
    import re

    puliti = []
    for errore in errori or []:
        testo = str(errore)
        trovato = re.fullmatch(r"\['(.*)'\]", testo, re.S)
        puliti.append(trovato.group(1) if trovato else testo)
    return puliti


# =============================================================== anagrafiche
@_strumento(annotazioni=CREAZIONE)
def crea_cliente(
    ragione_sociale: Annotated[str, Field(description="Ragione sociale o nome del contatto.")],
    tipo: Annotated[str, Field(description="Tipo di contatto: cliente, fornitore o entrambi.")] = "cliente",
    piva: Annotated[str, Field(description="Partita IVA (opzionale).")] = "",
    cf: Annotated[str, Field(description="Codice fiscale (opzionale).")] = "",
    email: Annotated[str, Field(description="Email (opzionale).")] = "",
    telefono: Annotated[str, Field(description="Telefono fisso (opzionale).")] = "",
    cellulare: Annotated[str, Field(description="Cellulare (opzionale).")] = "",
    indirizzo: Annotated[str, Field(description="Indirizzo (opzionale).")] = "",
    cap: Annotated[str, Field(description="CAP (opzionale).")] = "",
    citta: Annotated[str, Field(description="Città (opzionale).")] = "",
    provincia: Annotated[str, Field(description="Provincia, sigla di 2 lettere (opzionale).")] = "",
    pagamento: Annotated[str, Field(description="Condizione di pagamento per nome (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
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


@_strumento(annotazioni=MODIFICA)
def aggiorna_cliente(
    codice: Annotated[str, Field(description="Codice esatto del contatto (es. CLI00450).")],
    ragione_sociale: Annotated[Optional[str], Field(description="Nuova ragione sociale o nome (opzionale).")] = None,
    piva: Annotated[Optional[str], Field(description="Nuova partita IVA (opzionale).")] = None,
    cf: Annotated[Optional[str], Field(description="Nuovo codice fiscale (opzionale).")] = None,
    email: Annotated[Optional[str], Field(description="Nuova email (opzionale).")] = None,
    telefono: Annotated[Optional[str], Field(description="Nuovo telefono fisso (opzionale).")] = None,
    cellulare: Annotated[Optional[str], Field(description="Nuovo cellulare (opzionale).")] = None,
    indirizzo: Annotated[Optional[str], Field(description="Nuovo indirizzo (opzionale).")] = None,
    cap: Annotated[Optional[str], Field(description="Nuovo CAP (opzionale).")] = None,
    citta: Annotated[Optional[str], Field(description="Nuova città (opzionale).")] = None,
    provincia: Annotated[Optional[str], Field(description="Nuova provincia, sigla di 2 lettere (opzionale).")] = None,
    pagamento: Annotated[Optional[str], Field(description="Nuova condizione di pagamento per nome (opzionale).")] = None,
    sconto_vendite: Annotated[Optional[float], Field(ge=0, le=100, description="Sconto abituale di vendita in percentuale, 0-100 (opzionale).")] = None,
    sconto_acquisto: Annotated[Optional[float], Field(ge=0, le=100, description="Sconto base di acquisto in percentuale, 0-100 (opzionale).")] = None,
    attivo: Annotated[Optional[bool], Field(description="True per attivare il contatto, False per disattivarlo (opzionale).")] = None,
    note: Annotated[Optional[str], Field(description="Nuove note libere (opzionale).")] = None,
) -> dict:
    """Aggiorna i dati di un cliente o fornitore esistente, individuato per codice.
    I campi non indicati restano invariati: specificarne almeno uno."""
    from apps.contacts.models import Contact

    contatto = Contact.objects.filter(code=(codice or "").strip()).first()
    if contatto is None:
        raise ValueError(f"Nessun contatto con codice {codice!r}.")
    aggiornati = []
    campi_testo = {
        "name": ragione_sociale,
        "vat_number": piva,
        "tax_code": cf,
        "email": email,
        "phone": telefono,
        "mobile": cellulare,
        "address": indirizzo,
        "zip_code": cap,
        "city": citta,
        "province": provincia,
        "notes": note,
    }
    for campo, valore in campi_testo.items():
        if valore is not None:
            setattr(contatto, campo, valore.strip())
            aggiornati.append(campo)
    if pagamento is not None:
        contatto.payment_term = _risolvi_pagamento(pagamento) if pagamento.strip() else None
        aggiornati.append("payment_term")
    if sconto_vendite is not None:
        contatto.sale_discount_pct = _dec(sconto_vendite)
        aggiornati.append("sale_discount_pct")
    if sconto_acquisto is not None:
        contatto.purchase_discount_pct = _dec(sconto_acquisto)
        aggiornati.append("purchase_discount_pct")
    if attivo is not None:
        contatto.active = bool(attivo)
        aggiornati.append("active")
    if not aggiornati:
        raise ValueError("Specificare almeno un campo da aggiornare.")
    contatto.full_clean()
    contatto.save(update_fields=aggiornati)
    contatto.refresh_from_db()
    return {
        "messaggio": f"Contatto {contatto.code} aggiornato.",
        "codice": contatto.code,
        "nome": contatto.name,
        "tipo": contatto.kind_label,
        "sconto_vendite": _valore(contatto.sale_discount_pct),
        "sconto_acquisto": _valore(contatto.purchase_discount_pct),
        "attivo": contatto.active,
    }


@_strumento(annotazioni=CREAZIONE)
def crea_articolo(
    nome: Annotated[str, Field(description="Nome dell'articolo.")],
    um: Annotated[str, Field(description="Codice dell'unità di misura (es. pz, kg, m).")],
    prezzo_vendita: Annotated[float, Field(ge=0, description="Prezzo di vendita (opzionale, 0).")] = 0,
    prezzo_acquisto: Annotated[float, Field(ge=0, description="Prezzo di acquisto (opzionale, 0).")] = 0,
    categoria: Annotated[str, Field(description="Categoria: creata se non esiste (opzionale).")] = "",
    iva_vendita: Annotated[str, Field(description="Aliquota IVA di vendita per codice o percentuale (opzionale).")] = "",
    iva_acquisto: Annotated[str, Field(description="Aliquota IVA di acquisto per codice o percentuale (opzionale).")] = "",
    fornitore: Annotated[str, Field(description="Fornitore abituale per codice o nome (opzionale).")] = "",
    barcode: Annotated[str, Field(description="Codice a barre (opzionale).")] = "",
    scorta_minima: Annotated[float, Field(ge=0, description="Scorta minima (opzionale, 0).")] = 0,
    gestito_a_magazzino: Annotated[bool, Field(description="True se la giacenza è gestita a magazzino.")] = True,
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
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


@_strumento(annotazioni=MODIFICA)
def aggiorna_prezzo_articolo(
    codice: Annotated[str, Field(description="Codice esatto dell'articolo.")],
    prezzo_vendita: Annotated[Optional[float], Field(ge=0, description="Nuovo prezzo di vendita (opzionale).")] = None,
    prezzo_acquisto: Annotated[Optional[float], Field(ge=0, description="Nuovo prezzo di acquisto (opzionale).")] = None,
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
    prodotto.refresh_from_db()
    return {
        "messaggio": f"Prezzi di {prodotto.code} aggiornati.",
        "codice": prodotto.code,
        "prezzo_vendita": _valore(prodotto.sale_price),
        "prezzo_acquisto": _valore(prodotto.purchase_price),
    }


# ================================================================= magazzino
@_strumento(annotazioni=CREAZIONE)
def registra_movimento_magazzino(
    articolo: Annotated[str, Field(description="Codice o nome dell'articolo.")],
    tipo: Annotated[str, Field(description="Tipo di movimento: carico, scarico o rettifica.")],
    quantita: Annotated[float, Field(description="Quantità: valore assoluto per carico e scarico; differenza (anche negativa) per la rettifica.")],
    magazzino: Annotated[str, Field(description="Magazzino per codice o nome (opzionale: predefinito).")] = "",
    prezzo: Annotated[Optional[float], Field(ge=0, description="Costo unitario (opzionale).")] = None,
    riferimento: Annotated[str, Field(description="Riferimento esterno (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
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
        user=utente_sistema(),
    )
    return {
        "messaggio": f"Movimento registrato per {prodotto.code}.",
        "articolo": prodotto.code,
        "tipo": movimento.get_movement_type_display(),
        "quantita": _valore(movimento.quantity),
        "giacenza_attuale": _valore(prodotto.total_stock),
    }


# ================================================================ preventivi
@_strumento(annotazioni=CREAZIONE)
def crea_preventivo(
    cliente: Annotated[str, Field(description="Cliente per codice esatto o nome (se univoco).")],
    righe: Annotated[list[dict], Field(description="Righe del documento: dizionari con tipo (articolo|sezione|sottosezione|nota), descrizione, articolo, quantita, um, prezzo, sconto_pct, iva.")],
    data: Annotated[str, Field(description="Data del documento (opzionale: oggi).")] = "",
    valido_fino_al: Annotated[str, Field(description="Data di validità del preventivo (opzionale).")] = "",
    riferimento: Annotated[str, Field(description="Riferimento esterno (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
    condizioni: Annotated[str, Field(description="Condizioni contrattuali (opzionale).")] = "",
    pagamento: Annotated[str, Field(description="Condizione di pagamento per nome (opzionale).")] = "",
    cantiere: Annotated[str, Field(description="Cantiere per codice o nome (opzionale).")] = "",
    provvigione_a: Annotated[str, Field(description="Beneficiario della provvigione, codice o nome (opzionale).")] = "",
    provvigione_pct: Annotated[float, Field(ge=0, le=100, description="Percentuale di provvigione 0-100 (opzionale, 0).")] = 0,
) -> dict:
    """Crea un preventivo. righe è una lista di dizionari, uno per riga:
    {tipo: articolo|sezione|sottosezione|nota, descrizione, articolo, quantita, um, prezzo,
    sconto_pct, iva}. Per le righe articolo basta l'articolo (codice o nome) o la descrizione;
    prezzo, um e IVA si prendono dall'articolo se non indicati."""
    from django.db import transaction
    from django.utils import timezone

    from apps.sales.models import Quote, QuoteLine

    righe_valide = _normalizza_righe(righe)
    with transaction.atomic():
        preventivo = Quote(
            customer=_risolvi_contatto(cliente),
            created_by=utente_sistema(),
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
        _espandi_kit(preventivo, "quote")
        preventivo.recalculate()
    return {"messaggio": f"Preventivo {preventivo.number} creato.", **_riepilogo(preventivo), "righe_create": numero_righe}


@_strumento(annotazioni=MODIFICA)
def cambia_stato_preventivo(
    numero: Annotated[str, Field(description="Numero esatto del preventivo.")],
    stato: Annotated[str, Field(description="Nuovo stato: bozza, inviato, accettato o rifiutato.")],
) -> dict:
    """Cambia lo stato di un preventivo: bozza, inviato, accettato o rifiutato. Le transizioni
    seguono l'interfaccia del gestionale: inviato solo da bozza, accettato da bozza o inviato,
    rifiutato da bozza, inviato o accettato. Per la conversione in ordine usare
    converti_preventivo_in_ordine."""
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    codice = _stato_codice(stato, Quote.STATUS_CHOICES, campo="stato")
    if codice is None:
        raise ValueError("Specificare il nuovo stato.")
    if preventivo.status == Quote.STATUS_CONVERTED:
        raise ValueError("Preventivo già convertito in ordine: lo stato non si modifica.")
    if codice == Quote.STATUS_CONVERTED:
        raise ValueError("Per convertire il preventivo usa converti_preventivo_in_ordine.")
    if preventivo.status == codice:
        raise ValueError(f"Il preventivo è già in stato «{preventivo.get_status_display()}».")
    ammessi = {
        Quote.STATUS_SENT: {Quote.STATUS_DRAFT},
        Quote.STATUS_ACCEPTED: {Quote.STATUS_DRAFT, Quote.STATUS_SENT},
        Quote.STATUS_REJECTED: {Quote.STATUS_DRAFT, Quote.STATUS_SENT, Quote.STATUS_ACCEPTED},
    }
    if preventivo.status not in ammessi.get(codice, set()):
        etichette = dict(Quote.STATUS_CHOICES)
        raise ValueError(
            f"Da «{preventivo.get_status_display()}» non si passa a «{etichette.get(codice, codice)}»: "
            "usa un altro stato o l'interfaccia del gestionale."
        )
    preventivo.status = codice
    preventivo.save(update_fields=["status"])
    return {"messaggio": f"Preventivo {preventivo.number}: stato «{preventivo.get_status_display()}».", **_riepilogo(preventivo)}


@_strumento(annotazioni=CREAZIONE)
def duplica_preventivo(numero: Annotated[str, Field(description="Numero esatto del preventivo da duplicare.")]) -> dict:
    """Duplica un preventivo esistente in una nuova bozza, righe comprese."""
    from apps.sales import services as sales_services
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    copia = sales_services.duplicate_quote(preventivo, user=utente_sistema())
    return {"messaggio": f"Preventivo {preventivo.number} duplicato.", **_riepilogo(copia)}


@_strumento(annotazioni=MODIFICA_RIPETIBILE)
def converti_preventivo_in_ordine(numero: Annotated[str, Field(description="Numero esatto del preventivo da convertire.")]) -> dict:
    """Converte un preventivo in ordine cliente: copia testata e righe e segna il preventivo come
    convertito."""
    from apps.sales import services as sales_services
    from apps.sales.models import Quote

    preventivo = _risolvi_documento(Quote, numero, "preventivo")
    ordine = sales_services.convert_quote_to_order(preventivo, user=utente_sistema())
    return {
        "messaggio": f"Ordine {ordine.number} creato dal preventivo {preventivo.number}.",
        **_riepilogo(ordine),
        "da_preventivo": preventivo.number,
    }


# ========================================================= ordini cliente
@_strumento(annotazioni=CREAZIONE)
def crea_ordine_cliente(
    cliente: Annotated[str, Field(description="Cliente per codice esatto o nome (se univoco).")],
    righe: Annotated[list[dict], Field(description="Righe del documento: dizionari con tipo (articolo|sezione|sottosezione|nota), descrizione, articolo, quantita, um, prezzo, sconto_pct, iva.")],
    data: Annotated[str, Field(description="Data del documento (opzionale: oggi).")] = "",
    consegna_prevista: Annotated[str, Field(description="Data di consegna prevista (opzionale).")] = "",
    riferimento: Annotated[str, Field(description="Riferimento esterno (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
    condizioni: Annotated[str, Field(description="Condizioni contrattuali (opzionale).")] = "",
    pagamento: Annotated[str, Field(description="Condizione di pagamento per nome (opzionale).")] = "",
    cantiere: Annotated[str, Field(description="Cantiere per codice o nome (opzionale).")] = "",
    provvigione_a: Annotated[str, Field(description="Beneficiario della provvigione, codice o nome (opzionale).")] = "",
    provvigione_pct: Annotated[float, Field(ge=0, le=100, description="Percentuale di provvigione 0-100 (opzionale, 0).")] = 0,
) -> dict:
    """Crea un ordine cliente in bozza. righe ha lo stesso formato di crea_preventivo."""
    from django.db import transaction
    from django.utils import timezone

    from apps.sales.models import SalesOrder, SalesOrderLine

    righe_valide = _normalizza_righe(righe)
    with transaction.atomic():
        ordine = SalesOrder(
            customer=_risolvi_contatto(cliente),
            created_by=utente_sistema(),
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
        _espandi_kit(ordine, "order")
        ordine.recalculate()
    return {"messaggio": f"Ordine {ordine.number} creato in bozza.", **_riepilogo(ordine), "righe_create": numero_righe}


@_strumento(annotazioni=MODIFICA)
def conferma_ordine(
    numero: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")],
    rifornisci: Annotated[bool, Field(description="True per riportare le giacenze almeno alla scorta minima negli ordini fornitore generati.")] = False,
) -> dict:
    """Conferma un ordine cliente: fissa i costi per la marginalità ed eventualmente genera gli
    ordini fornitore per le quantità mancanti. Con rifornisci=True riporta le giacenze a scorta
    minima negli ordini fornitore generati."""
    from apps.sales import services as sales_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero, "ordine")
    esito = sales_services.confirm_sales_order(ordine, user=utente_sistema(), replenish=bool(rifornisci))
    ordine.refresh_from_db()
    return {
        "messaggio": f"Ordine {ordine.number} confermato.",
        **_riepilogo(ordine),
        "stato": ordine.get_status_display(),
        "ordini_fornitore_generati": [str(po) for po in esito.get("purchase_orders", [])],
        "articoli_senza_fornitore": [str(p) for p in esito.get("without_supplier", [])],
    }


@_strumento(annotazioni=MODIFICA)
def registra_consegna_ordine(
    numero: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")],
    magazzino: Annotated[str, Field(description="Magazzino per codice o nome (opzionale: predefinito).")] = "",
) -> dict:
    """Registra la consegna di un ordine cliente: consegna tutte le quantità residue e, per gli
    articoli gestiti a magazzino, registra gli scarichi. Se tutto è consegnato l'ordine passa a
    «Consegnato»."""
    from apps.sales import services as sales_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero, "ordine")
    warehouse = _risolvi_magazzino(magazzino) if magazzino else None
    errori = sales_services.deliver_sales_order(ordine, user=utente_sistema(), warehouse=warehouse)
    ordine.refresh_from_db()
    return {
        "messaggio": f"Consegna registrata per l'ordine {ordine.number}.",
        **_riepilogo(ordine),
        "stato": ordine.get_status_display(),
        "consegnato_il": _valore(ordine.delivered_at),
        "avvisi": _avvisi(errori),
    }


@_strumento(annotazioni=MODIFICA)
def annulla_ordine_cliente(numero: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")]) -> dict:
    """Annulla un ordine cliente non ancora consegnato (nessuna riga consegnata)."""
    from apps.sales import services as sales_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero, "ordine")
    sales_services.cancel_sales_order(ordine, user=utente_sistema())
    ordine.refresh_from_db()
    return {"messaggio": f"Ordine {ordine.number} annullato.", "numero": ordine.number, "stato": ordine.get_status_display()}


# ===================================================================== DDT
@_strumento(annotazioni=CREAZIONE)
def crea_ddt_da_ordine(numero_ordine: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")]) -> dict:
    """Crea un DDT in bozza dalle quantità ancora da consegnare di un ordine cliente."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    ddt = billing_services.create_delivery_note_from_order(ordine, user=utente_sistema())
    return {
        "messaggio": f"DDT {ddt.number} creato dall'ordine {ordine.number}.",
        "numero": ddt.number,
        "data": _valore(ddt.date),
        "cliente": ddt.customer.name,
    }


@_strumento(annotazioni=MODIFICA)
def emetti_ddt(
    numero: Annotated[str, Field(description="Numero esatto del DDT in bozza.")],
    magazzino: Annotated[str, Field(description="Magazzino per codice o nome (opzionale: predefinito).")] = "",
) -> dict:
    """Emette un DDT: scarica la merce dal magazzino, aggiorna le quantità consegnate
    dell'ordine collegato e, se l'ordine risulta completo, lo segna come consegnato."""
    from apps.billing import services as billing_services
    from apps.billing.models import DeliveryNote

    ddt = _risolvi_documento(DeliveryNote, numero, "DDT")
    warehouse = _risolvi_magazzino(magazzino) if magazzino else None
    errori = billing_services.issue_delivery_note(ddt, user=utente_sistema(), warehouse=warehouse)
    ddt.refresh_from_db()
    return {
        "messaggio": f"DDT {ddt.number} emesso.",
        "numero": ddt.number,
        "stato": ddt.get_status_display(),
        "emesso_il": _valore(ddt.issued_at),
        "avvisi": _avvisi(errori),
    }


@_strumento(annotazioni=MODIFICA)
def annulla_ddt(numero: Annotated[str, Field(description="Numero esatto del DDT in bozza.")]) -> dict:
    """Annulla un DDT ancora in bozza. Un DDT emesso non si annulla: serve una nota di reso o di credito."""
    from apps.billing import services as billing_services
    from apps.billing.models import DeliveryNote

    ddt = _risolvi_documento(DeliveryNote, numero, "DDT")
    billing_services.cancel_delivery_note(ddt)
    ddt.refresh_from_db()
    return {"messaggio": f"DDT {ddt.number} annullato.", "numero": ddt.number, "stato": ddt.get_status_display()}


# ============================================================ fatture emesse
@_strumento(annotazioni=CREAZIONE)
def crea_fattura_da_ordine(
    numero_ordine: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")],
    solo_consegnate: Annotated[bool, Field(description="True per fatturare solo le quantità già consegnate.")] = False,
) -> dict:
    """Crea una fattura emessa in bozza da un ordine cliente. Con solo_consegnate=True fattura solo
    le quantità già consegnate."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    fattura = billing_services.create_sales_invoice_from_order(
        ordine, user=utente_sistema(), only_delivered=bool(solo_consegnate)
    )
    return {"messaggio": f"Fattura {fattura.number} creata dall'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento(annotazioni=CREAZIONE)
def crea_fattura_da_ddt(numero_ddt: Annotated[str, Field(description="Numero esatto del DDT emesso.")]) -> dict:
    """Crea una fattura emessa in bozza da un DDT già emesso."""
    from apps.billing import services as billing_services
    from apps.billing.models import DeliveryNote

    ddt = _risolvi_documento(DeliveryNote, numero_ddt, "DDT")
    fattura = billing_services.create_sales_invoice_from_delivery_note(ddt, user=utente_sistema())
    return {"messaggio": f"Fattura {fattura.number} creata dal DDT {ddt.number}.", **_riepilogo(fattura)}


@_strumento(annotazioni=CREAZIONE)
def crea_acconto_ordine(
    numero_ordine: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")],
    percentuale: Annotated[Optional[float], Field(gt=0, le=100, description="Percentuale sull'imponibile (alternativa a importo).")] = None,
    importo: Annotated[Optional[float], Field(gt=0, description="Importo fisso (alternativa a percentuale).")] = None,
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
        user=utente_sistema(),
    )
    return {"messaggio": f"Acconto {fattura.number} creato sull'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento(annotazioni=CREAZIONE)
def crea_saldo_ordine(numero_ordine: Annotated[str, Field(description="Numero esatto dell'ordine cliente.")]) -> dict:
    """Crea la fattura di saldo di un ordine cliente, scalando gli eventuali acconti già emessi."""
    from apps.billing import services as billing_services
    from apps.sales.models import SalesOrder

    ordine = _risolvi_documento(SalesOrder, numero_ordine, "ordine")
    fattura = billing_services.create_order_balance(ordine, user=utente_sistema())
    return {"messaggio": f"Saldo {fattura.number} creato sull'ordine {ordine.number}.", **_riepilogo(fattura)}


@_strumento(annotazioni=CREAZIONE)
def crea_fattura_cantiere(
    codice: Annotated[str, Field(description="Codice o nome del cantiere.")],
    tipo: Annotated[str, Field(description="Tipo di fattura: acconto, sal o saldo.")],
    percentuale: Annotated[Optional[float], Field(gt=0, le=100, description="Percentuale: sull'imponibile per l'acconto, avanzamento 0-100 per il SAL (alternativa a importo per l'acconto).")] = None,
    importo: Annotated[Optional[float], Field(gt=0, description="Importo fisso per l'acconto (alternativa a percentuale).")] = None,
) -> dict:
    """Crea in bozza l'acconto, un SAL o il saldo di un cantiere. tipo: acconto, sal o saldo.
    L'acconto richiede percentuale oppure importo; il SAL richiede la percentuale di avanzamento
    (0-100); il saldo non richiede importi. Gli importi sono sempre al netto di quanto già fatturato."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    tipi = {
        "acconto": SalesInvoice.KIND_ADVANCE,
        "sal": SalesInvoice.KIND_SAL,
        "saldo": SalesInvoice.KIND_BALANCE,
    }
    codice_tipo = (tipo or "").strip().lower()
    if codice_tipo not in tipi:
        raise ValueError("Tipo non valido: usa acconto, sal o saldo.")
    if codice_tipo == "acconto" and (percentuale is None) == (importo is None):
        raise ValueError("Per l'acconto specifica percentuale oppure importo (uno dei due).")
    cantiere = _risolvi_cantiere(codice)
    fattura = billing_services.create_job_invoice(
        cantiere,
        tipi[codice_tipo],
        percent=_dec(percentuale) if percentuale is not None else None,
        amount=_dec(importo) if importo is not None else None,
        user=utente_sistema(),
    )
    return {
        "messaggio": f"{fattura.kind_title} {fattura.number} creato per il cantiere {cantiere.code}.",
        **_riepilogo(fattura),
        "tipo": fattura.kind_title,
        "cantiere": cantiere.code,
    }


@_strumento(annotazioni=MODIFICA)
def emetti_fattura(numero: Annotated[str, Field(description="Numero esatto della fattura emessa in bozza.")]) -> dict:
    """Passa una fattura emessa da bozza a emessa."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    fattura = _risolvi_documento(SalesInvoice, numero, "fattura")
    billing_services.issue_sales_invoice(fattura)
    fattura.refresh_from_db()
    return {"messaggio": f"Fattura {fattura.number} emessa.", "numero": fattura.number, "stato": fattura.get_status_display()}


@_strumento(annotazioni=MODIFICA)
def segna_fattura_inviata(numero: Annotated[str, Field(description="Numero esatto della fattura emessa.")]) -> dict:
    """Segna una fattura emessa come inviata al cliente."""
    from apps.billing import services as billing_services
    from apps.billing.models import SalesInvoice

    fattura = _risolvi_documento(SalesInvoice, numero, "fattura")
    billing_services.mark_sales_invoice_sent(fattura)
    fattura.refresh_from_db()
    return {"messaggio": f"Fattura {fattura.number} inviata.", "numero": fattura.number, "stato": fattura.get_status_display()}


@_strumento(annotazioni=MODIFICA)
def segna_fattura_pagata(numero: Annotated[str, Field(description="Numero esatto della fattura emessa.")]) -> dict:
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
@_strumento(annotazioni=CREAZIONE)
def crea_fattura_ricevuta_da_ordine_fornitore(
    numero_ordine: Annotated[str, Field(description="Numero esatto dell'ordine fornitore.")],
    solo_ricevute: Annotated[bool, Field(description="True per considerare solo le quantità già ricevute.")] = False,
) -> dict:
    """Crea in bozza una fattura ricevuta da un ordine fornitore. Con solo_ricevute=True considera
    solo le quantità già ricevute."""
    from apps.billing import services as billing_services
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero_ordine, "ordine fornitore")
    fattura = billing_services.create_purchase_invoice_from_po(
        ordine, user=utente_sistema(), only_received=bool(solo_ricevute)
    )
    return {
        "messaggio": f"Fattura ricevuta {fattura.number} creata dall'ordine {ordine.number}.",
        **_riepilogo(fattura),
        "fornitore": fattura.supplier.name,
    }


@_strumento(annotazioni=MODIFICA)
def registra_fattura_ricevuta(numero: Annotated[str, Field(description="Numero esatto della fattura ricevuta in bozza.")]) -> dict:
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


@_strumento(annotazioni=MODIFICA)
def segna_fattura_ricevuta_pagata(numero: Annotated[str, Field(description="Numero esatto della fattura ricevuta.")]) -> dict:
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
@_strumento(annotazioni=CREAZIONE)
def crea_ordine_fornitore(
    fornitore: Annotated[str, Field(description="Fornitore per codice esatto o nome (se univoco).")],
    righe: Annotated[list[dict], Field(description="Righe del documento (stesso formato di crea_preventivo; prezzo e IVA predefiniti di acquisto).")],
    data: Annotated[str, Field(description="Data del documento (opzionale: oggi).")] = "",
    consegna_prevista: Annotated[str, Field(description="Data di consegna prevista (opzionale).")] = "",
    cantiere: Annotated[str, Field(description="Cantiere per codice o nome (opzionale).")] = "",
    ordine_cliente: Annotated[str, Field(description="Numero dell'ordine cliente di origine (opzionale).")] = "",
    pagamento: Annotated[str, Field(description="Condizione di pagamento per nome (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
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
            created_by=utente_sistema(),
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
        _espandi_kit(ordine, "po")
        ordine.recalculate()
    return {
        "messaggio": f"Ordine fornitore {ordine.number} creato.",
        **_riepilogo(ordine),
        "fornitore": ordine.supplier.name,
        "righe_create": numero_righe,
    }


@_strumento(annotazioni=MODIFICA_RIPETIBILE)
def ricevi_ordine_fornitore(
    numero: Annotated[str, Field(description="Numero esatto dell'ordine fornitore.")],
    magazzino: Annotated[str, Field(description="Magazzino per codice o nome (opzionale: predefinito).")] = "",
    righe: Annotated[Optional[list[dict]], Field(description="Ricezione parziale: lista di {posizione, quantita}. Vuoto = tutte le quantità residue.")] = None,
) -> dict:
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
    ricevute, errori = purchasing_services.receive_purchase_order(
        ordine, quantities, user=utente_sistema(), warehouse=warehouse
    )
    ordine.refresh_from_db()
    return {
        "messaggio": f"Ricezione registrata per l'ordine {ordine.number}.",
        "numero": ordine.number,
        "stato": ordine.get_status_display(),
        "righe_ricevute": len(ricevute),
        "avvisi": _avvisi(errori),
    }


@_strumento(annotazioni=MODIFICA)
def invia_ordine_fornitore(numero: Annotated[str, Field(description="Numero esatto dell'ordine fornitore in bozza.")]) -> dict:
    """Segna un ordine fornitore in bozza come inviato al fornitore."""
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero, "ordine fornitore")
    if ordine.status != PurchaseOrder.STATUS_DRAFT:
        raise ValueError(f"L'ordine {ordine.number} non è in bozza: stato non modificato.")
    ordine.status = PurchaseOrder.STATUS_SENT
    ordine.save(update_fields=["status"])
    return {
        "messaggio": f"Ordine fornitore {ordine.number} segnato come inviato.",
        "numero": ordine.number,
        "stato": ordine.get_status_display(),
    }


@_strumento(annotazioni=MODIFICA)
def conferma_ordine_fornitore(numero: Annotated[str, Field(description="Numero esatto dell'ordine fornitore.")]) -> dict:
    """Segna un ordine fornitore come confermato dal fornitore (da bozza o inviato)."""
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero, "ordine fornitore")
    if ordine.status not in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SENT}:
        raise ValueError(f"L'ordine {ordine.number} non può essere confermato nello stato attuale.")
    ordine.status = PurchaseOrder.STATUS_CONFIRMED
    ordine.save(update_fields=["status"])
    return {
        "messaggio": f"Ordine fornitore {ordine.number} confermato.",
        "numero": ordine.number,
        "stato": ordine.get_status_display(),
    }


@_strumento(annotazioni=MODIFICA)
def annulla_ordine_fornitore(numero: Annotated[str, Field(description="Numero esatto dell'ordine fornitore.")]) -> dict:
    """Annulla un ordine fornitore non ancora ricevuto (nessuna riga ricevuta)."""
    from apps.purchasing import services as purchasing_services
    from apps.purchasing.models import PurchaseOrder

    ordine = _risolvi_documento(PurchaseOrder, numero, "ordine fornitore")
    purchasing_services.cancel_purchase_order(ordine, user=utente_sistema())
    ordine.refresh_from_db()
    return {
        "messaggio": f"Ordine fornitore {ordine.number} annullato.",
        "numero": ordine.number,
        "stato": ordine.get_status_display(),
    }


@_strumento(annotazioni=MODIFICA_RIPETIBILE)
def applica_variazione_listino(
    listino: Annotated[str, Field(description="Nome del listino (anche parziale, se univoco).")],
    percentuale: Annotated[float, Field(description="Variazione percentuale: positiva aumenta i prezzi, negativa li diminuisce (diversa da 0).")],
    fornitore: Annotated[str, Field(description="Parte del nome del fornitore per disambiguare (opzionale).")] = "",
) -> dict:
    """Applica una variazione percentuale a tutte le voci di un listino fornitore: positiva
    aumenta i prezzi, negativa li diminuisce. ``fornitore`` restringe la ricerca del listino."""
    from apps.purchasing import services as purchasing_services

    prezzo_lista = _risolvi_listino(listino, fornitore)
    variazione = purchasing_services.apply_pricelist_adjustment(
        prezzo_lista, _dec(percentuale), user=utente_sistema()
    )
    return {
        "messaggio": f"Listino «{prezzo_lista.name}» aggiornato: {variazione.items_count} voci.",
        "listino": prezzo_lista.name,
        "fornitore": prezzo_lista.supplier.name,
        "variazione_pct": _valore(variazione.percent),
        "voci_aggiornate": variazione.items_count,
    }


# ============================================== commesse, lead, manutenzioni
@_strumento(annotazioni=CREAZIONE)
def crea_cantiere(
    cliente: Annotated[str, Field(description="Cliente per codice esatto o nome (se univoco).")],
    nome: Annotated[str, Field(description="Nome del cantiere.")],
    indirizzo: Annotated[str, Field(description="Indirizzo (opzionale).")] = "",
    cap: Annotated[str, Field(description="CAP (opzionale).")] = "",
    citta: Annotated[str, Field(description="Città (opzionale).")] = "",
    provincia: Annotated[str, Field(description="Provincia, sigla di 2 lettere (opzionale).")] = "",
    inizio: Annotated[str, Field(description="Data di inizio (opzionale).")] = "",
    fine_prevista: Annotated[str, Field(description="Data di fine prevista (opzionale).")] = "",
    responsabile: Annotated[str, Field(description="Username del responsabile (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
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


@_strumento(annotazioni=CREAZIONE)
def crea_lead(
    nome: Annotated[str, Field(description="Nome del lead.")],
    fase: Annotated[str, Field(description="Fase del lead per nome (opzionale: prima fase in corso).")] = "",
    contatto: Annotated[str, Field(description="Contatto esistente per codice o nome (opzionale).")] = "",
    telefono: Annotated[str, Field(description="Telefono (opzionale).")] = "",
    email: Annotated[str, Field(description="Email (opzionale).")] = "",
    citta: Annotated[str, Field(description="Città (opzionale).")] = "",
    provenienza: Annotated[str, Field(description="Provenienza del lead (opzionale).")] = "",
    valore_stimato: Annotated[float, Field(ge=0, description="Valore stimato (opzionale, 0).")] = 0,
    prossima_azione: Annotated[str, Field(description="Data della prossima azione (opzionale).")] = "",
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
) -> dict:
    """Crea un lead commerciale. fase è opzionale (altrimenti la prima fase in corso);
    contatto è un cliente/fornitore esistente (opzionale)."""
    from apps.leads.models import Lead, LeadStage

    lead = Lead(
        name=(nome or "").strip(),
        created_by=utente_sistema(),
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


@_strumento(annotazioni=MODIFICA)
def cambia_fase_lead(
    nome_lead: Annotated[str, Field(description="Nome del lead (o parte, se univoco).")],
    fase: Annotated[str, Field(description="Nuova fase per nome, oppure «avanti» per la fase successiva.")],
) -> dict:
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


@_strumento(annotazioni=MODIFICA_RIPETIBILE)
def registra_manutenzione(
    descrizione: Annotated[str, Field(description="Descrizione della manutenzione (o parte, se univoca).")],
    cliente: Annotated[str, Field(description="Parte del nome del cliente per disambiguare (opzionale).")] = "",
) -> dict:
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


# ================================================================= personale
@_strumento(annotazioni=CREAZIONE)
def crea_dipendente(
    nome: Annotated[str, Field(description="Nome del dipendente.")],
    cognome: Annotated[str, Field(description="Cognome del dipendente.")],
    mansione: Annotated[str, Field(description="Mansione o qualifica (opzionale).")] = "",
    email: Annotated[str, Field(description="Email (opzionale).")] = "",
    telefono: Annotated[str, Field(description="Telefono (opzionale).")] = "",
    codice_fiscale: Annotated[str, Field(description="Codice fiscale (opzionale).")] = "",
    assunzione: Annotated[str, Field(description="Data di assunzione (opzionale).")] = "",
    costo_orario: Annotated[Optional[float], Field(ge=0, description="Costo orario (opzionale).")] = None,
    ore_settimanali: Annotated[float, Field(gt=0, le=168, description="Ore settimanali contrattuali (1-168).")] = 40,
    ferie_annue: Annotated[float, Field(ge=0, le=365, description="Giorni di ferie annue (0-365).")] = 26,
    permessi_annui: Annotated[float, Field(ge=0, le=2000, description="Ore di permessi annui (0-2000).")] = 0,
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
) -> dict:
    """Crea un dipendente. assunzione è la data (AAAA-MM-GG o GG/MM/AAAA)."""
    from apps.hr.models import Employee

    dipendente = Employee(
        first_name=(nome or "").strip(),
        last_name=(cognome or "").strip(),
        qualification=(mansione or "").strip(),
        email=(email or "").strip(),
        phone=(telefono or "").strip(),
        fiscal_code=(codice_fiscale or "").strip(),
        hired_on=_data(assunzione, "assunzione"),
        contract_weekly_hours=_dec(ore_settimanali, default=40),
        holiday_days_per_year=_dec(ferie_annue, default=26),
        rol_hours_per_year=_dec(permessi_annui, default=0),
        notes=note or "",
    )
    if not dipendente.first_name or not dipendente.last_name:
        raise ValueError("Nome e cognome del dipendente sono obbligatori.")
    if costo_orario is not None:
        dipendente.hourly_cost = _dec(costo_orario)
    dipendente.full_clean()
    dipendente.save()
    return {
        "messaggio": f"Dipendente {dipendente.code} creato.",
        "codice": dipendente.code,
        "nome": dipendente.full_name,
        "mansione": dipendente.qualification,
    }


@_strumento(annotazioni=CREAZIONE)
def crea_collaboratore(
    nome: Annotated[str, Field(description="Nome del collaboratore.")],
    azienda: Annotated[str, Field(description="Azienda di appartenenza (opzionale).")] = "",
    specializzazione: Annotated[str, Field(description="Specializzazione (opzionale).")] = "",
    email: Annotated[str, Field(description="Email (opzionale).")] = "",
    telefono: Annotated[str, Field(description="Telefono (opzionale).")] = "",
    codice_fiscale: Annotated[str, Field(description="Codice fiscale (opzionale).")] = "",
    tariffa_oraria: Annotated[Optional[float], Field(ge=0, description="Tariffa oraria (opzionale).")] = None,
    note: Annotated[str, Field(description="Note libere (opzionale).")] = "",
) -> dict:
    """Crea un collaboratore esterno (scavo, elettricista, piastrellista…)."""
    from apps.hr.models import Collaborator

    collaboratore = Collaborator(
        name=(nome or "").strip(),
        company=(azienda or "").strip(),
        specialization=(specializzazione or "").strip(),
        email=(email or "").strip(),
        phone=(telefono or "").strip(),
        fiscal_code=(codice_fiscale or "").strip(),
        notes=note or "",
    )
    if not collaboratore.name:
        raise ValueError("Il nome del collaboratore è obbligatorio.")
    if tariffa_oraria is not None:
        collaboratore.hourly_rate = _dec(tariffa_oraria)
    collaboratore.full_clean()
    collaboratore.save()
    return {
        "messaggio": f"Collaboratore {collaboratore.code} creato.",
        "codice": collaboratore.code,
        "nome": collaboratore.name,
        "azienda": collaboratore.company,
    }


@_strumento(annotazioni=CREAZIONE)
def registra_ore(
    dipendente: Annotated[str, Field(description="Dipendente per codice esatto o nome (se univoco).")],
    ore: Annotated[float, Field(ge=0.25, le=24, description="Ore lavorate nella giornata (0,25-24).")],
    data: Annotated[str, Field(description="Data (opzionale: oggi).")] = "",
    tipo: Annotated[str, Field(description="Tipo di ore: ordinario, straordinario o trasferta.")] = "ordinario",
    cantiere: Annotated[str, Field(description="Cantiere per codice o nome (opzionale).")] = "",
    descrizione: Annotated[str, Field(description="Descrizione dell'attività (opzionale).")] = "",
    addebitabile: Annotated[bool, Field(description="True se addebitabile al cliente.")] = False,
) -> dict:
    """Registra le ore di un dipendente in una giornata. tipo: ordinario, straordinario o
    trasferta. Le ore vanno da 0,25 a 24 (frazioni di quarto d'ora)."""
    from django.utils import timezone

    from apps.hr.models import TimeEntry

    dipendente_obj = _risolvi_dipendente(dipendente)
    codice_tipo = _stato_codice(tipo or "ordinario", TimeEntry.KIND_CHOICES, campo="tipo")
    if codice_tipo is None:
        raise ValueError("Specificare il tipo di ore: ordinario, straordinario o trasferta.")
    ore_dec = _dec(ore)
    if ore_dec < _dec("0.25") or ore_dec > _dec("24"):
        raise ValueError("Le ore devono essere fra 0,25 e 24.")
    voce = TimeEntry(
        employee=dipendente_obj,
        created_by=utente_sistema(),
        date=_data(data, "data") or timezone.localdate(),
        hours=ore_dec,
        kind=codice_tipo,
        description=(descrizione or "").strip(),
        billable=bool(addebitabile),
    )
    if cantiere:
        voce.job = _risolvi_cantiere(cantiere)
    voce.save()
    return {
        "messaggio": f"Registrate {voce.hours} ore per {dipendente_obj.full_name}.",
        "id": voce.pk,
        "dipendente": dipendente_obj.full_name,
        "codice": dipendente_obj.code,
        "data": _valore(voce.date),
        "ore": _valore(voce.hours),
        "tipo": voce.get_kind_display(),
        "cantiere": voce.job.name if voce.job_id else "",
    }


@_strumento(annotazioni=CREAZIONE)
def registra_ore_collaboratore(
    collaboratore: Annotated[str, Field(description="Collaboratore per codice esatto o nome (se univoco).")],
    ore: Annotated[float, Field(ge=0.25, le=24, description="Ore rendicontate (0,25-24).")],
    data: Annotated[str, Field(description="Data (opzionale: oggi).")] = "",
    cantiere: Annotated[str, Field(description="Cantiere per codice o nome (opzionale).")] = "",
    descrizione: Annotated[str, Field(description="Descrizione dell'attività (opzionale).")] = "",
) -> dict:
    """Registra le ore rendicontate da un collaboratore esterno (0,25–24 ore al giorno)."""
    from django.utils import timezone

    from apps.hr.models import CollaboratorTimeEntry

    collaboratore_obj = _risolvi_collaboratore(collaboratore)
    ore_dec = _dec(ore)
    if ore_dec < _dec("0.25") or ore_dec > _dec("24"):
        raise ValueError("Le ore devono essere fra 0,25 e 24.")
    voce = CollaboratorTimeEntry(
        collaborator=collaboratore_obj,
        created_by=utente_sistema(),
        date=_data(data, "data") or timezone.localdate(),
        hours=ore_dec,
        description=(descrizione or "").strip(),
    )
    if cantiere:
        voce.job = _risolvi_cantiere(cantiere)
    voce.save()
    return {
        "messaggio": f"Registrate {voce.hours} ore per {collaboratore_obj.name}.",
        "id": voce.pk,
        "collaboratore": collaboratore_obj.name,
        "codice": collaboratore_obj.code,
        "data": _valore(voce.date),
        "ore": _valore(voce.hours),
        "cantiere": voce.job.name if voce.job_id else "",
    }


@_strumento(annotazioni=CREAZIONE)
def registra_assenza(
    dipendente: Annotated[str, Field(description="Dipendente per codice esatto o nome (se univoco).")],
    tipo: Annotated[str, Field(description="Tipo di assenza: ferie, rol, malattia, non retribuito o altro.")],
    dal: Annotated[str, Field(description="Data di inizio.")],
    al: Annotated[str, Field(description="Data di fine (opzionale: stesso giorno).")] = "",
    ore: Annotated[Optional[float], Field(gt=0, le=24, description="Ore del permesso orario, solo per un giorno (opzionale).")] = None,
    motivo: Annotated[str, Field(description="Motivo (opzionale).")] = "",
) -> dict:
    """Registra un'assenza (ferie, permessi (rol), malattia, non retribuito, altro) in stato
    «Richiesta». «ore» vale solo per un permesso di poche ore nello stesso giorno.
    Usa cambia_stato_assenza per approvarla o rifiutarla."""
    from apps.hr.models import LeaveRequest

    dipendente_obj = _risolvi_dipendente(dipendente)
    codice_tipo = _stato_codice(tipo, LeaveRequest.KIND_CHOICES, campo="tipo")
    if codice_tipo is None:
        raise ValueError("Specificare il tipo di assenza: ferie, rol, malattia, non retribuito o altro.")
    inizio = _data(dal, "dal")
    if inizio is None:
        raise ValueError("Specificare la data di inizio (dal).")
    fine = _data(al, "al") or inizio
    if fine < inizio:
        raise ValueError("La data di fine non può precedere quella di inizio.")
    assenza = LeaveRequest(
        employee=dipendente_obj,
        created_by=utente_sistema(),
        kind=codice_tipo,
        start_date=inizio,
        end_date=fine,
        reason=(motivo or "").strip(),
    )
    if ore is not None:
        if inizio != fine:
            raise ValueError("Un permesso orario vale per un solo giorno: lascia vuoto «al» o indica la stessa data.")
        assenza.hours = _dec(ore)
        if assenza.hours <= 0:
            raise ValueError("Le ore del permesso devono essere positive.")
    assenza.save()
    return {
        "messaggio": f"Assenza registrata per {dipendente_obj.full_name} ({assenza.duration_label}).",
        "id": assenza.pk,
        "dipendente": dipendente_obj.full_name,
        "tipo": assenza.get_kind_display(),
        "dal": _valore(assenza.start_date),
        "al": _valore(assenza.end_date),
        "stato": assenza.get_status_display(),
    }


@_strumento(annotazioni=MODIFICA)
def cambia_stato_assenza(
    id: Annotated[int, Field(ge=1, description="Id dell'assenza (da lista_assenze).")],
    stato: Annotated[str, Field(description="Nuovo stato: approvata, rifiutata o annullata.")],
) -> dict:
    """Cambia lo stato di un'assenza: approvata, rifiutata o annullata. L'id arriva da lista_assenze."""
    from apps.hr.models import LeaveRequest

    try:
        assenza = LeaveRequest.objects.select_related("employee").get(pk=int(id))
    except (TypeError, ValueError):
        raise ValueError("Id assenza non valido.")
    except LeaveRequest.DoesNotExist:
        raise ValueError(f"Nessuna assenza con id {int(id)!r}.")
    codice = (stato or "").strip().lower()
    if codice in {"approvata", "approva", "approvato"}:
        assenza.approve(utente_sistema())
    elif codice in {"rifiutata", "rifiuta", "rifiutato"}:
        assenza.reject(utente_sistema())
    elif codice in {"annullata", "annulla", "annullato"}:
        assenza.status = LeaveRequest.STATUS_CANCELLED
        assenza.save(update_fields=["status", "updated_at"])
    else:
        raise ValueError("Stato non valido: usa approvata, rifiutata o annullata.")
    return {
        "messaggio": f"Assenza di {assenza.employee.full_name}: stato «{assenza.get_status_display()}».",
        "id": assenza.pk,
        "dipendente": assenza.employee.full_name,
        "tipo": assenza.get_kind_display(),
        "stato": assenza.get_status_display(),
    }
