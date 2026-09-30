"""Importazione articoli da file CSV o Excel.

Formato file (intestazioni riconosciute, ordine libero, colonne extra ignorate):

    campo            | obbligatorio | descrizione
    -----------------|--------------|-------------------------------------------
    descrizione      | sì           | nome dell'articolo
    codice           | no           | codice articolo (se esiste viene aggiornato)
    categoria        | no           | categoria (creata se assente)
    unita_misura     | no           | codice o nome dell'unità (es. PZ, KG)
    prezzo_vendita   | no           | prezzo di vendita
    iva_vendita      | no           | codice aliquota (22, 10, N2.2…) o valore (22)
    prezzo_acquisto  | no           | prezzo di acquisto (aggiorna anche il listino)
    iva_acquisto     | no           | aliquota di acquisto
    barcode          | no           | codice a barre
    scorta_minima    | no           | scorta minima
    fornitore        | no           | fornitore abituale (creato se assente)
    etichette        | no           | etichette separate da virgola (create se assenti)
    note             | no           | note interne
    attivo           | no           | sì/no (default sì)
"""
import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

HEADER_ALIASES = {
    "code": {"codice", "code", "sku", "codice_articolo", "cod_articolo"},
    "name": {"descrizione", "nome", "name", "articolo", "prodotto", "description", "descrizione_articolo"},
    "category_name": {"categoria", "category", "gruppo", "famiglia"},
    "uom_name": {"unita_misura", "unita", "um", "uom", "unita_di_misura", "udm", "unita_di_vendita"},
    "sale_price": {"prezzo_vendita", "prezzo", "price", "prezzo_1", "listino_vendita"},
    "sale_vat": {"iva_vendita", "iva", "vat", "aliquota", "aliquota_iva"},
    "purchase_price": {"prezzo_acquisto", "costo", "cost", "prezzo_fornitore", "prezzo_netto"},
    "purchase_vat": {"iva_acquisto", "iva_fornitore", "aliquota_acquisto"},
    "barcode": {"barcode", "ean", "codice_a_barre", "cod_barre"},
    "min_stock": {"scorta_minima", "scorta", "scorta_min", "min_stock", "quantita_minima"},
    "supplier_name": {"fornitore", "supplier", "ragione_sociale_fornitore", "nome_fornitore"},
    "tags": {"etichette", "tags", "tag"},
    "notes": {"note", "notes", "annotazioni"},
    "active": {"attivo", "active", "abilitato"},
}

COLUMN_DOCS = [
    ("descrizione", "sì", "Nome dell'articolo", "Bullone M8 zincato"),
    ("codice", "no", "Codice articolo: se già esistente l'articolo viene aggiornato", "ART00012"),
    ("categoria", "no", "Categoria (creata se non esiste)", "Ricambi"),
    ("unita_misura", "no", "Codice o nome dell'unità di misura", "PZ"),
    ("prezzo_vendita", "no", "Prezzo di vendita (senza IVA)", "0,35"),
    ("iva_vendita", "no", "Codice aliquota o valore (default: aliquota vendite predefinita)", "22"),
    ("prezzo_acquisto", "no", "Prezzo di acquisto dal fornitore (senza IVA)", "0,18"),
    ("iva_acquisto", "no", "Aliquota di acquisto (default: aliquota acquisti predefinita)", "22"),
    ("barcode", "no", "Codice a barre / EAN", "8012345678901"),
    ("scorta_minima", "no", "Scorta minima per l'avviso sotto scorta", "500"),
    ("fornitore", "no", "Fornitore abituale (creato se non esiste)", "Ferramenta Bianchi S.p.A."),
    ("etichette", "no", "Etichette separate da virgola (create se non esistono)", "Promozione, Nuovo"),
    ("note", "no", "Note interne", ""),
    ("attivo", "no", "sì / no (default sì)", "sì"),
]

CATEGORY_FIELD_HELP = {
    "descrizione": "name",
    "codice": "code",
    "categoria": "category_name",
    "unita_misura": "uom_name",
    "prezzo_vendita": "sale_price",
    "iva_vendita": "sale_vat",
    "prezzo_acquisto": "purchase_price",
    "iva_acquisto": "purchase_vat",
    "barcode": "barcode",
    "scorta_minima": "min_stock",
    "fornitore": "supplier_name",
    "etichette": "tags",
    "note": "notes",
    "attivo": "active",
}


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    price_items: int = 0
    errors: list = field(default_factory=list)
    examples: list = field(default_factory=list)

    @property
    def processed(self):
        return self.created + self.updated


# ----------------------------------------------------------------- analisi
def canonical_header(value):
    text = str(value or "").strip().lower()
    for source, target in (("à", "a"), ("è", "e"), ("é", "e"), ("ì", "i"), ("ò", "o"), ("ù", "u"), ("°", "")):
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    for canonical, aliases in HEADER_ALIASES.items():
        if text in aliases:
            return canonical
    return None


def _cell_to_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_csv(file_obj):
    raw = file_obj.read()
    text = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Impossibile leggere il file: codifica non riconosciuta.")

    sample = text[:4000]
    delimiter = ";"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        # Fallback: usa il separatore più frequente nella prima riga
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        counts = {d: first_line.count(d) for d in ";,\t|"}
        delimiter = max(counts, key=counts.get) if any(counts.values()) else ";"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [[_cell_to_text(cell) for cell in row] for row in reader]


def parse_xlsx(file_obj):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Supporto Excel non installato (openpyxl).") from exc

    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    rows = [[_cell_to_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
    workbook.close()
    return rows


def read_table(file_obj):
    """Legge il file e restituisce la lista di righe come dizionari normalizzati."""
    filename = (getattr(file_obj, "name", "") or "").lower()
    if filename.endswith((".xlsx", ".xlsm")):
        raw_rows = parse_xlsx(file_obj)
    else:
        raw_rows = parse_csv(file_obj)

    raw_rows = [row for row in raw_rows if any(str(cell).strip() for cell in row)]
    if not raw_rows:
        raise ValueError("Il file non contiene righe.")

    column_map = {}
    for index, header in enumerate(raw_rows[0]):
        canonical = canonical_header(header)
        if canonical:
            column_map[index] = canonical
    if "name" not in column_map.values():
        raise ValueError("Colonna «descrizione» (o «nome») non trovata nella prima riga. Scarica il modello CSV per un esempio.")

    table = []
    for raw_row in raw_rows[1:]:
        row = {}
        for index, canonical in column_map.items():
            row[canonical] = raw_row[index] if index < len(raw_row) else ""
        table.append(row)
    return table


# ------------------------------------------------------------- conversioni
def parse_decimal(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        # 1.234,56 → 1234.56
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"valore numerico non valido: «{value}»")


def parse_bool(value, default=True):
    if value in (None, ""):
        return default
    return str(value).strip().lower() not in {"0", "no", "false", "falso", "n", "disattivo"}


def resolve_vat(value, default):
    from apps.core.models import VatRate

    text = str(value or "").strip()
    if not text:
        return default
    rate = VatRate.objects.filter(code__iexact=text, is_active=True).first()
    if rate:
        return rate
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if match:
        number = Decimal(match.group(0).replace(",", "."))
        rate = VatRate.objects.filter(rate=number, is_active=True).first()
        if rate:
            return rate
    return default


def resolve_uom(value):
    from apps.core.models import UnitOfMeasure

    text = str(value or "").strip()
    if not text:
        return None
    uom = UnitOfMeasure.objects.filter(code__iexact=text).first() or UnitOfMeasure.objects.filter(name__iexact=text).first()
    if uom:
        return uom
    code = text.upper()[:10]
    uom = UnitOfMeasure.objects.filter(code=code).first()
    if uom:
        return uom
    return UnitOfMeasure.objects.create(code=code, name=text.capitalize())


def default_uom():
    from apps.core.models import UnitOfMeasure

    return UnitOfMeasure.objects.filter(code="PZ").first() or UnitOfMeasure.objects.first()


# ---------------------------------------------------------------- import
def import_products(rows, *, default_supplier=None, update_pricelist=False, user=None):
    """Importa le righe normalizzate. Restituisce un ImportReport."""
    from django.utils import timezone

    from apps.contacts.models import Contact
    from apps.core.models import Tag, VatRate
    from apps.purchasing.models import PriceListItem, SupplierPriceList

    from .models import Category, Product

    report = ImportReport()
    fallback_uom = default_uom()
    fallback_sale_vat = VatRate.default_for_sales()
    fallback_purchase_vat = VatRate.default_for_purchase()

    def pricelist_for(supplier):
        pricelist = SupplierPriceList.objects.filter(supplier=supplier, is_active=True).order_by("-valid_from", "-pk").first()
        if pricelist is None:
            pricelist = SupplierPriceList.objects.create(
                supplier=supplier,
                name=f"Listino {timezone.localdate().year}",
                created_by=user,
                notes="Creato automaticamente dall'importazione articoli.",
            )
        return pricelist

    for row_number, row in enumerate(rows, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            report.errors.append((row_number, "Descrizione mancante: riga saltata."))
            continue

        try:
            sale_price = parse_decimal(row.get("sale_price"))
            purchase_price = parse_decimal(row.get("purchase_price"))
            min_stock = parse_decimal(row.get("min_stock"))
        except ValueError as exc:
            report.errors.append((row_number, f"{name}: {exc}"))
            continue

        supplier = None
        supplier_name = (row.get("supplier_name") or "").strip()
        if supplier_name:
            supplier = Contact.objects.filter(name__iexact=supplier_name).first()
            if supplier is None:
                supplier = Contact.objects.create(name=supplier_name, is_customer=False, is_supplier=True)
                report.examples.append(f"Creato fornitore «{supplier_name}».")
        elif default_supplier is not None:
            supplier = default_supplier

        try:
            code = (row.get("code") or "").strip()
            product = None
            if code:
                product = Product.objects.filter(code__iexact=code).first()
            if product is None:
                product = Product.objects.filter(name__iexact=name).first()

            uom = resolve_uom(row.get("uom_name")) if row.get("uom_name") else None

            if product is None:
                product = Product(
                    name=name,
                    uom=uom or fallback_uom,
                    sale_vat=resolve_vat(row.get("sale_vat"), fallback_sale_vat),
                    purchase_vat=resolve_vat(row.get("purchase_vat"), fallback_purchase_vat),
                    sale_price=sale_price if sale_price is not None else Decimal("0"),
                    purchase_price=purchase_price if purchase_price is not None else Decimal("0"),
                )
                if code:
                    product.code = code
                created = True
            else:
                created = False
                product.name = name
                if code:
                    product.code = code
                if uom:
                    product.uom = uom
                if sale_price is not None:
                    product.sale_price = sale_price
                if purchase_price is not None:
                    product.purchase_price = purchase_price
                if row.get("sale_vat"):
                    product.sale_vat = resolve_vat(row.get("sale_vat"), product.sale_vat)
                if row.get("purchase_vat"):
                    product.purchase_vat = resolve_vat(row.get("purchase_vat"), product.purchase_vat)

            if supplier is not None:
                product.main_supplier = supplier
            if min_stock is not None:
                product.min_stock = min_stock
            if row.get("barcode"):
                product.barcode = row["barcode"].strip()
            if row.get("notes"):
                product.notes = row["notes"].strip()
            product.active = parse_bool(row.get("active"), default=True)

            category_name = (row.get("category_name") or "").strip()
            if category_name:
                category, _ = Category.objects.get_or_create(name=category_name)
                product.category = category

            product.save()

            if row.get("tags"):
                for tag_name in re.split(r"[,;]", row["tags"]):
                    tag_name = tag_name.strip()
                    if tag_name:
                        tag, _ = Tag.objects.get_or_create(name=tag_name)
                        product.tags.add(tag)

            if update_pricelist and supplier is not None and purchase_price is not None:
                pricelist = pricelist_for(supplier)
                item, item_created = PriceListItem.objects.get_or_create(
                    pricelist=pricelist, product=product, defaults={"price": purchase_price}
                )
                if not item_created and item.price != purchase_price:
                    item.price = purchase_price
                    item.save(update_fields=["price", "updated_at"])
                report.price_items += 1

            if created:
                report.created += 1
            else:
                report.updated += 1

        except Exception as exc:  # pragma: no cover - protezione generica per riga
            report.errors.append((row_number, f"{name}: {exc}"))

    return report


def build_template_csv():
    """CSV di esempio con intestazioni e due righe dimostrative."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    headers = [column for column, _required, _desc, _example in COLUMN_DOCS]
    writer.writerow(headers)
    writer.writerow(["ART00001", "Bullone M8 zincato", "Ricambi", "PZ", "0,35", "22", "0,18", "22", "8012345678901", "500", "Ferramenta Bianchi S.p.A.", "Promozione", "", "sì"])
    writer.writerow(["", "Montaggio in cantiere", "Servizi", "H", "45,00", "22", "0", "22", "", "0", "", "", "Tariffa oraria", "sì"])
    return "\ufeff" + output.getvalue()
