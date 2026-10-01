"""Lettura di DDT e fatture acquisiti: OCR del testo e riconoscimento dei dati.

L'OCR usa Tesseract (pytesseract) per immagini e PDF. Se Tesseract non è
installato (es. Windows in sviluppo) la funzione resta disponibile ma segnala
che l'OCR non è attivo: il documento viene comunque salvato e la fattura si
può compilare a mano.
"""
import re
import shutil
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings

DATE_RE = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
NUMBER_RE = re.compile(
    r"(?:ddt|d\.d\.t\.?|documento|doc\.?|fattura|ft\.?)\s*(?:n\.?|num\.?|numero|nr\.?)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-\/\.]{0,19})",
    re.IGNORECASE,
)
TOTAL_RE = re.compile(
    r"totale\s*(?:documento|ddt|fattura|merce|generale)?\s*[:\-]?\s*(?:€|eur\.?)?\s*([0-9\.]+,[0-9]{2}|[0-9]+\.[0-9]{2})",
    re.IGNORECASE,
)
VAT_RE = re.compile(r"\b(\d{11})\b")
QTY_LINE_RE = re.compile(
    r"^(?P<desc>.{4,}?)\s+(?P<qty>\d{1,4}(?:[.,]\d{1,3})?)\s*(?P<uom>pz|nr\.?|kg|gr|mt|mq|mc|lt|ml|cf|box|plt|h|gg)\.?$",
    re.IGNORECASE,
)
QTY_UOM_FIRST_RE = re.compile(
    r"^(?P<desc>.{4,}?)\s+(?P<uom>pz|nr\.?|kg|gr|mt|mq|mc|lt|ml|cf|box|plt|h|gg)\s+(?P<qty>\d{1,4}(?:[.,]\d{1,3})?)\.?$",
    re.IGNORECASE,
)


def ocr_available():
    """True se Tesseract e pytesseract sono disponibili."""
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def extract_text(file_obj, language=None):
    """Estrae il testo dal documento (immagine o PDF)."""
    import pytesseract
    from PIL import Image

    language = language or getattr(settings, "OCR_LANGUAGES", "ita+eng")
    name = (getattr(file_obj, "name", "") or "").lower()

    if name.endswith(".pdf"):
        from pdf2image import convert_from_bytes

        pages = convert_from_bytes(file_obj.read(), dpi=200, first_page=1, last_page=5)
        return "\n".join(pytesseract.image_to_string(page, lang=language) for page in pages).strip()

    image = Image.open(file_obj)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return pytesseract.image_to_string(image, lang=language).strip()


def parse_italian_decimal(text):
    text = text.strip().replace("€", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_document_text(text):
    """Ricava numero, data, totale e fornitore dal testo letto."""
    from apps.contacts.models import Contact

    result = {"doc_number": "", "doc_date": None, "total_amount": None, "supplier": None}

    match = DATE_RE.search(text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year < 100:
            year += 2000
        try:
            result["doc_date"] = date(year, month, day)
        except ValueError:
            pass

    number_match = NUMBER_RE.search(text)
    if number_match:
        candidate = number_match.group(1).strip(" .,-")
        if candidate and not DATE_RE.match(candidate):
            result["doc_number"] = candidate[:50]

    total_match = TOTAL_RE.search(text)
    if total_match:
        result["total_amount"] = parse_italian_decimal(total_match.group(1))

    lowered = text.lower()
    compact = text.replace(" ", "")
    best = None
    for contact in Contact.objects.filter(is_supplier=True)[:500]:
        score = 0.0
        if contact.vat_number:
            vat = re.sub(r"\D", "", contact.vat_number)
            if vat and vat in compact:
                score = 10.0
        if not score:
            tokens = [token for token in re.split(r"\W+", contact.name.lower()) if len(token) >= 4]
            if tokens:
                hits = sum(1 for token in tokens if token in lowered)
                score = hits / len(tokens) if hits else 0.0
        if score and (best is None or score > best[0]):
            best = (score, contact)
    if best and best[0] >= 0.6:
        result["supplier"] = best[1]

    return result


def guess_lines(text, limit=40):
    """Prova a ricavare le righe (descrizione + quantità) dal testo.

    Riconosce sia «descrizione 10 PZ» sia «descrizione PZ 10».
    """
    rows = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if len(line) < 6:
            continue
        match = QTY_LINE_RE.match(line) or QTY_UOM_FIRST_RE.match(line)
        if match:
            description = match.group("desc").strip(" .,-")
            if description and not re.fullmatch(r"[\W\d]+", description):
                rows.append({"description": description[:200], "qty": match.group("qty").replace(",", ".")})
        if len(rows) >= limit:
            break
    return rows


def process_scan(scan):
    """Elabora un documento acquisito: estrae testo e dati principali."""
    from .models import ScannedDocument

    if not ocr_available():
        scan.status = ScannedDocument.STATUS_ERROR
        scan.error_message = (
            "OCR non disponibile su questo sistema (manca Tesseract): il file resta salvato, "
            "compila la fattura a mano."
        )
        scan.save(update_fields=["status", "error_message"])
        return scan

    try:
        text = extract_text(scan.file)
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente
        scan.status = ScannedDocument.STATUS_ERROR
        scan.error_message = f"Errore durante l'OCR: {exc}"[:300]
        scan.save(update_fields=["status", "error_message"])
        return scan

    data = parse_document_text(text)
    scan.extracted_text = text
    scan.doc_number = data["doc_number"]
    scan.doc_date = data["doc_date"]
    scan.total_amount = data["total_amount"]
    scan.supplier = data["supplier"]
    scan.status = ScannedDocument.STATUS_OK
    scan.error_message = ""
    scan.save(update_fields=["extracted_text", "doc_number", "doc_date", "total_amount", "supplier", "status", "error_message"])
    return scan
