"""Fatturazione elettronica: generazione dell'XML FatturaPA (versione FPR12) e invio via PEC.

Il file generato segue lo schema del Sistema di Interscambio (versione 1.2);
la trasmissione avviene per PEC verso l'indirizzo dello SDI usando le
credenziali SMTP configurate (variabili EMAIL_*), mentre gli esiti
(consegnata/accettata/scartata) si aggiornano dalla scheda della fattura.
"""
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from apps.core.models import CompanySettings
from apps.sales.models import round2

from .models import SalesInvoice

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"


def _q(tag):
    return f"{{{NS}}}{tag}"


def _sub(parent, tag, text=None):
    element = ET.SubElement(parent, _q(tag))
    if text is not None:
        element.text = str(text)
    return element


def _money(value):
    return f"{round2(value or 0):.2f}"


def _clean_vat(value):
    cleaned = (value or "").strip().upper().replace(" ", "")
    if cleaned.startswith("IT") and len(cleaned) > 11:
        cleaned = cleaned[2:]
    return cleaned


def _country_code(entity):
    country = (getattr(entity, "country", "") or "").strip()
    if not country or country.lower() in {"italia", "italy", "it"}:
        return "IT"
    return country.upper()[:2]


def validate_for_sdi(invoice):
    """Controlla i dati necessari alla fattura elettronica. Restituisce la lista errori."""
    company = CompanySettings.load()
    customer = invoice.customer
    errors = []

    if not company.vat_number:
        errors.append("manca la partita IVA dell'azienda (Impostazioni → Dati azienda)")
    if not company.address or not company.zip_code or not company.city:
        errors.append("manca l'indirizzo completo dell'azienda (Impostazioni → Dati azienda)")
    if not (customer.vat_number or customer.tax_code):
        errors.append(f"per «{customer.name}» manca partita IVA o codice fiscale")
    if not customer.sdi_code and not customer.pec:
        errors.append(f"per «{customer.name}» manca il codice destinatario SDI o la PEC")
    if customer.sdi_code and len(customer.sdi_code.strip()) != 7:
        errors.append("il codice destinatario SDI deve avere 7 caratteri (es. 0000000 o XXXXXXX)")
    if not invoice.lines.exists():
        errors.append("la fattura non contiene righe")
    for line in invoice.lines.select_related("vat_rate"):
        if line.vat_rate is None:
            errors.append(f"riga «{line.description or line.pk}»: manca l'aliquota IVA")
        elif line.vat_rate.rate == 0 and not line.vat_rate.nature:
            errors.append(
                f"riga «{line.description or line.pk}»: per l'aliquota a 0% serve il codice natura IVA (es. N1, N2.2) "
                "impostato nell'aliquota"
            )
    return errors


def build_fattura_xml(invoice):
    """Costruisce il file XML FatturaPA della fattura. Solleva ValidationError se mancano dati."""
    errors = validate_for_sdi(invoice)
    if errors:
        raise ValidationError(errors)

    company = CompanySettings.load()
    customer = invoice.customer

    ET.register_namespace("", NS)
    root = ET.Element(_q("FatturaElettronica"), {"versione": "FPR12"})

    header = _sub(root, "FatturaElettronicaHeader")

    # ---------------------------------------------------- DatiTrasmissione
    transmission = _sub(header, "DatiTrasmissione")
    id_trasmittente = _sub(transmission, "IdTrasmittente")
    _sub(id_trasmittente, "IdPaese", "IT")
    _sub(id_trasmittente, "IdCodice", _clean_vat(company.vat_number))
    _sub(transmission, "ProgressivoInvio", f"{invoice.pk:05d}")
    _sub(transmission, "FormatoTrasmissione", "FPR12")
    sdi_code = (customer.sdi_code or "").strip().upper()
    if len(sdi_code) == 7:
        _sub(transmission, "CodiceDestinatario", sdi_code)
        if customer.pec:
            _sub(transmission, "PECDestinatario", customer.pec)
    else:
        _sub(transmission, "CodiceDestinatario", "0000000")
        _sub(transmission, "PECDestinatario", customer.pec)

    # ------------------------------------------------- CedentePrestatore
    cedente = _sub(header, "CedentePrestatore")
    dati = _sub(cedente, "DatiAnagrafici")
    id_fiscale = _sub(dati, "IdFiscaleIVA")
    _sub(id_fiscale, "IdPaese", "IT")
    _sub(id_fiscale, "IdCodice", _clean_vat(company.vat_number))
    if company.tax_code:
        _sub(dati, "CodiceFiscale", company.tax_code.strip().upper())
    anagrafica = _sub(dati, "Anagrafica")
    _sub(anagrafica, "Denominazione", company.name)
    _sub(dati, "RegimeFiscale", company.fiscal_regime or "RF01")
    sede = _sub(cedente, "Sede")
    _sub(sede, "Indirizzo", company.address)
    _sub(sede, "CAP", company.zip_code)
    _sub(sede, "Comune", company.city)
    if company.province:
        _sub(sede, "Provincia", company.province.upper()[:2])
    _sub(sede, "Nazione", _country_code(company))

    # -------------------------------------------- CessionarioCommittente
    cessionario = _sub(header, "CessionarioCommittente")
    dati2 = _sub(cessionario, "DatiAnagrafici")
    if customer.vat_number:
        id_fiscale2 = _sub(dati2, "IdFiscaleIVA")
        _sub(id_fiscale2, "IdPaese", _country_code(customer))
        _sub(id_fiscale2, "IdCodice", _clean_vat(customer.vat_number))
    if customer.tax_code:
        _sub(dati2, "CodiceFiscale", customer.tax_code.strip().upper())
    anagrafica2 = _sub(dati2, "Anagrafica")
    _sub(anagrafica2, "Denominazione", customer.name)
    sede2 = _sub(cessionario, "Sede")
    _sub(sede2, "Indirizzo", customer.address or "-")
    _sub(sede2, "CAP", customer.zip_code or "00000")
    _sub(sede2, "Comune", customer.city or "-")
    if customer.province:
        _sub(sede2, "Provincia", customer.province.upper()[:2])
    _sub(sede2, "Nazione", _country_code(customer))

    # --------------------------------------------------------------- Body
    body = _sub(root, "FatturaElettronicaBody")
    generali = _sub(body, "DatiGenerali")
    documento = _sub(generali, "DatiGeneraliDocumento")
    # Gli acconti si trasmettono come TD02 (acconto/anticipo su fattura); SAL e
    # saldi sono fatture normali (TD01).
    _sub(documento, "TipoDocumento", "TD02" if invoice.kind == SalesInvoice.KIND_ADVANCE else "TD01")
    _sub(documento, "Divisa", "EUR")
    _sub(documento, "Data", invoice.date.isoformat())
    _sub(documento, "Numero", invoice.number)
    _sub(documento, "ImportoTotaleDocumento", _money(invoice.grand_total))
    if invoice.is_job_document:
        parti = [invoice.kind_title]
        if invoice.job_id:
            parti.append(str(invoice.job))
        if invoice.reference:
            parti.append(invoice.reference)
        causale = " – ".join(parti)[:200]
    else:
        causale = (invoice.reference or "Vendita").strip()[:200]
    if causale:
        _sub(documento, "Causale", causale)

    beni = _sub(body, "DatiBeniServizi")
    for index, line in enumerate(invoice.lines.select_related("vat_rate"), start=1):
        detail = _sub(beni, "DettaglioLinee")
        _sub(detail, "NumeroLinea", index)
        description = (line.description or (line.product.name if line.product_id else "") or "Voce")[:1000]
        _sub(detail, "Descrizione", description)
        _sub(detail, "Quantita", f"{Decimal(line.qty or 0):.2f}")
        if line.uom_id:
            _sub(detail, "UnitaMisura", line.uom.code[:10])
        _sub(detail, "PrezzoUnitario", _money(line.unit_price))
        if line.discount_pct:
            sconto = _sub(detail, "ScontoMaggiorazione")
            _sub(sconto, "Tipo", "SC")
            _sub(sconto, "Percentuale", _money(line.discount_pct))
        _sub(detail, "PrezzoTotale", _money(line.line_subtotal))
        _sub(detail, "AliquotaIVA", _money(line.vat_rate.rate))
        if line.vat_rate.nature:
            _sub(detail, "Natura", line.vat_rate.nature)

    for row in invoice.vat_breakdown():
        riepilogo = _sub(beni, "DatiRiepilogo")
        _sub(riepilogo, "AliquotaIVA", _money(row["rate"].rate))
        if row["rate"].nature:
            _sub(riepilogo, "Natura", row["rate"].nature)
        _sub(riepilogo, "ImponibileImporto", _money(row["base"]))
        _sub(riepilogo, "Imposta", _money(row["vat"]))
        if row["rate"].rate and not row["rate"].nature:
            _sub(riepilogo, "EsigibilitaIVA", "I")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@transaction.atomic
def save_invoice_xml(invoice):
    """Genera e salva il file XML sulla fattura."""
    xml_bytes = build_fattura_xml(invoice)
    filename = f"IT{_clean_vat(CompanySettings.load().vat_number)}_{invoice.pk:05d}.xml"
    invoice.xml_file.save(filename, ContentFile(xml_bytes), save=False)
    invoice.sdi_status = SalesInvoice.SDI_GENERATED
    invoice.sdi_note = ""
    invoice.save(update_fields=["xml_file", "sdi_status", "sdi_note", "updated_at"])
    return invoice.xml_file


def accoda_invoice_sdi(invoice):
    """Accoda l'XML per la trasmissione allo SDI via PEC (invio in background).

    Generare l'XML è veloce, la PEC può impiegare decine di secondi: la vista
    accoda e risponde subito, il comando ``invia_coda_email`` trasmette.
    """
    from apps.core.mailing import accoda_email
    from apps.core.models import EmailInCoda

    from .emailing import email_configured

    if not email_configured():
        raise ValidationError(
            "Configura prima l'invio email/PEC (variabili EMAIL_* nel file .env) per trasmettere allo SDI."
        )
    if invoice.status == SalesInvoice.STATUS_DRAFT:
        raise ValidationError("Emetti prima la fattura, poi trasmettila allo SDI.")
    if not invoice.xml_file:
        save_invoice_xml(invoice)

    customer = invoice.customer
    destination = (customer.sdi_code or customer.pec or "").strip()
    subject = f"Fattura {destination} {invoice.number}"
    with invoice.xml_file.open("rb") as handle:
        filename = invoice.xml_file.name.rsplit("/", 1)[-1]
        xml_bytes = handle.read()
    return accoda_email(
        to_email=settings.SDI_PEC_ADDRESS,
        subject=subject,
        message=f"Invio della fattura {invoice.number} al Sistema di Interscambio.",
        attachment=xml_bytes,
        attachment_name=filename,
        attachment_type="application/xml",
        descrizione=f"SDI {invoice.number} ({destination})",
        modello=EmailInCoda.MODELLO_FATTURA_SDI,
        oggetto_id=invoice.pk,
    )


def send_invoice_sdi(invoice):
    """Invia l'XML allo SDI per PEC (richiede SMTP/PEC configurato)."""
    from .emailing import email_configured

    if not email_configured():
        raise ValidationError(
            "Configura prima l'invio email/PEC (variabili EMAIL_* nel file .env) per trasmettere allo SDI."
        )
    if invoice.status == SalesInvoice.STATUS_DRAFT:
        raise ValidationError("Emetti prima la fattura, poi trasmettila allo SDI.")
    if not invoice.xml_file:
        save_invoice_xml(invoice)

    customer = invoice.customer
    destination = (customer.sdi_code or customer.pec or "").strip()
    subject = f"Fattura {destination} {invoice.number}"
    email = EmailMessage(
        subject=subject,
        body=f"Invio della fattura {invoice.number} al Sistema di Interscambio.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.SDI_PEC_ADDRESS],
    )
    with invoice.xml_file.open("rb") as handle:
        filename = invoice.xml_file.name.rsplit("/", 1)[-1]
        email.attach(filename, handle.read(), "application/xml")
    email.send(fail_silently=False)

    invoice.sdi_status = SalesInvoice.SDI_SENT
    invoice.sdi_sent_at = timezone.now()
    invoice.sdi_note = ""
    invoice.save(update_fields=["sdi_status", "sdi_sent_at", "sdi_note", "updated_at"])
    return invoice
