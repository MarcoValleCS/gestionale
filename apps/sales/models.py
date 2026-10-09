"""Preventivi e ordini cliente."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import NumberSequence, PaymentTerm, TimeStampedModel, UnitOfMeasure, VatRate

ZERO = Decimal("0")

# Gli arrotondamenti stanno in apps/core/rounding.py: qui restano importabili
# come prima (apps.sales.models.round2 / round3) per non rompere i chiamanti.
from apps.core.rounding import round2, round3, round4  # noqa: E402  (dopo ZERO per chiarezza)

# Tipi di riga (stile Odoo): le righe di testo non hanno prezzo e non entrano
# nei totali, servono solo a ordinare il documento. Una riga «sezione» apre un
# gruppo: tutto ciò che sta sotto le appartiene finché non arriva un'altra
# sezione, come in Odoo.
LINE_ARTICLE = "article"
LINE_SECTION = "section"
LINE_SUBSECTION = "subsection"
LINE_NOTE = "note"
LINE_TYPE_CHOICES = [
    (LINE_ARTICLE, "Articolo"),
    (LINE_SECTION, "Sezione"),
    (LINE_SUBSECTION, "Sottosezione"),
    (LINE_NOTE, "Nota"),
]
# Tipi che non hanno prodotto, quantità né prezzo (non toccano i totali)
DISPLAY_LINE_TYPES = {LINE_SECTION, LINE_SUBSECTION, LINE_NOTE}


class DocumentLine(TimeStampedModel):
    """Riga di documento (preventivo o ordine)."""

    position = models.PositiveIntegerField("Posizione", default=0)
    line_type = models.CharField(
        "Tipo riga",
        max_length=12,
        choices=LINE_TYPE_CHOICES,
        default=LINE_ARTICLE,
        help_text="Sezione, sottosezione e nota sono righe di testo: non hanno prezzo e non entrano nei totali.",
    )
    section = models.CharField(
        "Sezione",
        max_length=80,
        blank=True,
        help_text="Es. ambiente o fase (Bagno 1, Scavo, Finiture…). Righe consecutive con la stessa sezione vengono raggruppate.",
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Articolo"
    )
    description = models.CharField("Descrizione", max_length=300, blank=True)
    qty = models.DecimalField("Quantità", max_digits=12, decimal_places=3, default=Decimal("1"))
    uom = models.ForeignKey(
        UnitOfMeasure, on_delete=models.PROTECT, null=True, blank=True, related_name="+", verbose_name="U.d.M."
    )
    unit_price = models.DecimalField("Prezzo unitario", max_digits=12, decimal_places=4, default=ZERO)
    discount_pct = models.DecimalField("Sconto %", max_digits=5, decimal_places=2, default=ZERO)
    vat_rate = models.ForeignKey(
        VatRate, on_delete=models.PROTECT, null=True, blank=True, related_name="+", verbose_name="IVA"
    )

    class Meta:
        abstract = True
        ordering = ["position", "pk"]

    @property
    def is_display(self):
        """Vero per le righe di testo (sezione, sottosezione, nota)."""
        return self.line_type in DISPLAY_LINE_TYPES

    @property
    def line_subtotal(self):
        if self.is_display:
            return ZERO
        qty = Decimal(self.qty or 0)
        price = Decimal(self.unit_price or 0)
        discount = Decimal(self.discount_pct or 0)
        return round2(qty * price * (1 - discount / 100))

    @property
    def line_vat(self):
        rate = Decimal(self.vat_rate.rate) if self.vat_rate else ZERO
        return round2(self.line_subtotal * rate / 100)

    @property
    def line_total(self):
        return round2(self.line_subtotal + self.line_vat)

    @property
    def net_unit_price(self):
        """Prezzo unitario al netto dello sconto di riga.

        Serve ai documenti che vanno al cliente: lo sconto è una trattativa
        interna e non compare, quindi il prezzo mostrato dev'essere già quello
        effettivo.
        """
        prezzo = Decimal(self.unit_price or 0)
        sconto = Decimal(self.discount_pct or 0)
        return round4(prezzo * (1 - sconto / 100))

    @property
    def line_cost(self):
        """Costo della riga: costo fissato alla conferma, altrimenti prezzo di acquisto attuale.

        Lo sconto di riga NON si applica al costo: lo sconto fatto al cliente
        non riduce quanto si paga il fornitore.
        """
        if self.is_display:
            return ZERO
        cost = self.unit_cost
        if cost is None:
            cost = self.product.purchase_price if self.product_id else ZERO
        return Decimal(cost or 0) * Decimal(self.qty or 0)

    @property
    def label(self):
        if self.is_display:
            return self.description or "—"
        if self.product_id and self.description:
            return f"{self.product.code} – {self.description}" if self.product.code not in self.description else self.description
        return self.description or (str(self.product) if self.product_id else "—")


def group_lines_by_section(lines):
    """Raggruppa le righe sotto le sezioni, con subtotali per sezione e sottosezione.

    Una riga di tipo «sezione» apre il gruppo e ne diventa il titolo: tutte le
    righe che seguono appartengono a quella sezione finché non ne compare
    un'altra (come in Odoo). Allo stesso modo una «sottosezione» apre un blocco
    interno alla sezione, con il subtotale delle sole righe che stanno sotto di
    essa. Note e righe di testo non pesano nei totali.

    ``subtotal`` è l'imponibile, ``total`` è l'importo IVA inclusa (per le
    stampe al cliente): entrambi sommano le sole righe articolo.

    Restano supportate anche le vecchie sezioni scritte riga per riga (campo
    ``section``): righe consecutive con lo stesso testo formano un gruppo.
    """
    groups = []
    corrente = None
    blocco = None
    numero = 0

    def nuovo_gruppo(titolo, riga_sezione=None):
        gruppo = {
            "section": titolo,
            "lines": [],
            "subtotal": ZERO,
            "total": ZERO,
            "section_line": riga_sezione,
            "blocks": [],
            "has_articles": False,
        }
        groups.append(gruppo)
        return gruppo

    def nuovo_blocco(gruppo, titolo=""):
        blocco = {"subsection": titolo, "lines": [], "subtotal": ZERO, "total": ZERO, "has_articles": False}
        gruppo["blocks"].append(blocco)
        return blocco

    for line in lines:
        tipo = getattr(line, "line_type", LINE_ARTICLE) or LINE_ARTICLE
        if tipo == LINE_SECTION:
            corrente = nuovo_gruppo((line.description or "").strip(), line)
            blocco = nuovo_blocco(corrente)
            continue
        # Vecchio campo «section» per riga: vale solo per gli articoli dei
        # documenti storici (fatture/DDT/ordini fornitore lo usano ancora).
        # Se il documento usa già sezioni esplicite (riga «sezione»), il campo
        # legacy va ignorato: altrimenti un testo residuo spezzerebbe la
        # sezione esplicita creando gruppi spuri.
        sezione_legacy = getattr(line, "section", "") or ""
        if tipo != LINE_ARTICLE:
            sezione_legacy = ""
        if sezione_legacy:
            esplicita_attiva = corrente is not None and corrente.get("section_line") is not None
            if not esplicita_attiva and (corrente is None or corrente["section"] != sezione_legacy):
                corrente = nuovo_gruppo(sezione_legacy)
                blocco = nuovo_blocco(corrente)
        if corrente is None:
            corrente = nuovo_gruppo("")
        if blocco is None:
            blocco = nuovo_blocco(corrente)
        if tipo == LINE_SUBSECTION:
            # apre un blocco con subtotale proprio: non è una riga di elenco
            blocco = nuovo_blocco(corrente, (line.description or "").strip())
            continue
        if tipo == LINE_ARTICLE:
            numero += 1
            line.row_number = numero
            blocco["subtotal"] += line.line_subtotal
            corrente["subtotal"] += line.line_subtotal
            blocco["total"] += line.line_total
            corrente["total"] += line.line_total
            blocco["has_articles"] = True
            corrente["has_articles"] = True
        else:
            # nota: si mostra ma non conta
            line.row_number = None
        blocco["lines"].append(line)
        corrente["lines"].append(line)
    for group in groups:
        group["subtotal"] = round2(group["subtotal"])
        group["total"] = round2(group["total"])
        for block in group["blocks"]:
            block["subtotal"] = round2(block["subtotal"])
            block["total"] = round2(block["total"])
    return groups


class TotalsDocument(models.Model):
    """Documento con totali calcolati dalle righe."""

    subtotal = models.DecimalField("Imponibile", max_digits=12, decimal_places=2, default=ZERO)
    vat_total = models.DecimalField("Totale IVA", max_digits=12, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField("Totale documento", max_digits=12, decimal_places=2, default=ZERO)

    class Meta:
        abstract = True

    def recalculate(self, save=True):
        subtotal = ZERO
        vat = ZERO
        for line in self.lines.all():
            subtotal += line.line_subtotal
            vat += line.line_vat
        self.subtotal = round2(subtotal)
        self.vat_total = round2(vat)
        self.grand_total = round2(self.subtotal + self.vat_total)
        if save:
            self.save(update_fields=["subtotal", "vat_total", "grand_total"])
        return self

    def vat_breakdown(self):
        """Riepilogo IVA per aliquota: lista di dict {rate, base, vat}."""
        rows = {}
        for line in self.lines.select_related("vat_rate"):
            if line.vat_rate_id is None:
                continue
            entry = rows.setdefault(line.vat_rate_id, {"rate": line.vat_rate, "base": ZERO, "vat": ZERO})
            entry["base"] += line.line_subtotal
            entry["vat"] += line.line_vat
        ordered = sorted(rows.values(), key=lambda row: -Decimal(row["rate"].rate))
        for row in ordered:
            row["base"] = round2(row["base"])
            row["vat"] = round2(row["vat"])
        return ordered


class CommissionedDocument(models.Model):
    """Documento di vendita su cui può maturare una provvigione.

    Sta in un mixin separato e NON in ``TotalsDocument``: quello è condiviso
    anche da fatture e ordini fornitore, dove una provvigione sulle vendite non
    ha alcun senso.
    """

    commission_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_commissions",
        verbose_name="Provvigione a",
        help_text="Chi ha presentato il cliente e percepisce la provvigione.",
    )
    commission_pct = models.DecimalField(
        "Provvigione %",
        max_digits=5,
        decimal_places=2,
        default=ZERO,
        help_text="Percentuale sull'imponibile. Lascia a 0 se non c'è provvigione.",
    )

    class Meta:
        abstract = True

    @property
    def has_commission(self):
        return bool(self.commission_contact_id and self.commission_pct)

    @property
    def commission_amount(self):
        """Valore della provvigione in euro (percentuale sull'imponibile)."""
        if not self.has_commission:
            return ZERO
        return round2(Decimal(self.subtotal or 0) * Decimal(self.commission_pct) / 100)

    @property
    def margin_after_commission(self):
        """Imponibile meno il costo delle righe meno la provvigione."""
        cost = sum((line.line_cost for line in self.lines.all()), ZERO)
        return round2(Decimal(self.subtotal or 0) - cost - self.commission_amount)


class Quote(CommissionedDocument, TotalsDocument, TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CONVERTED = "converted"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_SENT, "Inviato"),
        (STATUS_ACCEPTED, "Accettato"),
        (STATUS_REJECTED, "Rifiutato"),
        (STATUS_CONVERTED, "Convertito in ordine"),
    ]

    number = models.CharField("Numero", max_length=30, unique=True, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    valid_until = models.DateField("Valido fino al", null=True, blank=True)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="quotes", verbose_name="Cliente")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes", verbose_name="Cantiere"
    )
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    reference = models.CharField("Vostro riferimento", max_length=100, blank=True)
    notes = models.TextField("Note interne", blank=True)
    terms_text = models.TextField("Condizioni (stampate)", blank=True)
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Preventivo"
        verbose_name_plural = "Preventivi"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="quote_status_date_idx"),
            models.Index(fields=["customer", "-date"], name="quote_customer_date_idx"),
        ]

    def __str__(self):
        return self.number or f"Preventivo {self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_QUOTE).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate() and self.status in {self.STATUS_DRAFT, self.STATUS_SENT})

    @property
    def is_editable(self):
        return self.status in {self.STATUS_DRAFT, self.STATUS_SENT}

    @property
    def generated_order(self):
        return self.generated_orders.order_by("-pk").first()


class QuoteLine(DocumentLine):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines", verbose_name="Preventivo")


class SalesOrder(CommissionedDocument, TotalsDocument, TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_CONFIRMED, "Confermato"),
        (STATUS_DELIVERED, "Consegnato"),
        (STATUS_CANCELLED, "Annullato"),
    ]

    number = models.CharField("Numero", max_length=30, unique=True, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    expected_date = models.DateField("Consegna prevista", null=True, blank=True)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="sales_orders", verbose_name="Cliente")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_orders", verbose_name="Cantiere"
    )
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    source_quote = models.ForeignKey(
        Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_orders", verbose_name="Da preventivo"
    )
    reference = models.CharField("Vostro riferimento", max_length=100, blank=True)
    notes = models.TextField("Note interne", blank=True)
    terms_text = models.TextField("Condizioni (stampate)", blank=True)
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    confirmed_at = models.DateTimeField("Confermato il", null=True, blank=True)
    delivered_at = models.DateTimeField("Consegnato il", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_orders", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Ordine cliente"
        verbose_name_plural = "Ordini cliente"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="order_status_date_idx"),
            models.Index(fields=["customer", "-date"], name="order_customer_date_idx"),
            # le statistiche leggono gli ordini consegnati per periodo: senza
            # questo indice ogni apertura della dashboard scorre tutta la tabella
            models.Index(fields=["status", "delivered_at"], name="order_delivered_idx"),
        ]

    def __str__(self):
        return self.number or f"Ordine {self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_SALES_ORDER).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status == self.STATUS_DRAFT

    @property
    def all_delivered(self):
        lines = [line for line in self.lines.all() if not line.is_display]
        if not lines:
            return False
        return all(line.qty_delivered >= line.qty for line in lines)

    @property
    def delivery_state(self):
        if self.status == self.STATUS_DELIVERED:
            return "delivered"
        lines = [line for line in self.lines.all() if not line.is_display]
        if lines and any(line.qty_delivered > 0 for line in lines) and not self.all_delivered:
            return "partially"
        return self.status


class SalesOrderLine(DocumentLine):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines", verbose_name="Ordine")
    qty_delivered = models.DecimalField("Quantità consegnata", max_digits=12, decimal_places=3, default=ZERO)
    unit_cost = models.DecimalField(
        "Costo unitario",
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Costo di acquisto al momento della conferma, usato per la marginalità.",
    )

    @property
    def qty_remaining(self):
        return round3(Decimal(self.qty or 0) - Decimal(self.qty_delivered or 0))


class QuoteTemplate(TimeStampedModel):
    """Modello di preventivo riutilizzabile (righe e condizioni preimpostate)."""

    name = models.CharField("Nome modello", max_length=120, unique=True)
    description = models.CharField("Descrizione", max_length=200, blank=True)
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    terms_text = models.TextField("Condizioni (stampate)", blank=True)
    notes = models.TextField("Note interne", blank=True)
    is_active = models.BooleanField("Attivo", default=True)
    sort_order = models.PositiveSmallIntegerField("Ordine di visualizzazione", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quote_templates",
        verbose_name="Creato da",
    )

    class Meta:
        verbose_name = "Modello di preventivo"
        verbose_name_plural = "Modelli di preventivo"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def lines_count(self):
        return self.lines.count()

    def value(self):
        return round2(sum((line.line_subtotal for line in self.lines.all()), ZERO))


class QuoteTemplateLine(DocumentLine):
    template = models.ForeignKey(QuoteTemplate, on_delete=models.CASCADE, related_name="lines", verbose_name="Modello")
