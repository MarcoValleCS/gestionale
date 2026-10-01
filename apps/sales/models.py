"""Preventivi e ordini cliente."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import NumberSequence, PaymentTerm, TimeStampedModel, UnitOfMeasure, VatRate

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")


def round2(value):
    return Decimal(value or 0).quantize(TWO_PLACES)


def round3(value):
    return Decimal(value or 0).quantize(THREE_PLACES)


class DocumentLine(TimeStampedModel):
    """Riga di documento (preventivo o ordine)."""

    position = models.PositiveIntegerField("Posizione", default=0)
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
    def line_subtotal(self):
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
    def label(self):
        if self.product_id and self.description:
            return f"{self.product.code} – {self.description}" if self.product.code not in self.description else self.description
        return self.description or (str(self.product) if self.product_id else "—")


def group_lines_by_section(lines):
    """Raggruppa righe consecutive con la stessa sezione, con subtotale per gruppo."""
    groups = []
    for number, line in enumerate(lines, start=1):
        line.row_number = number
        section = line.section or ""
        if not groups or groups[-1]["section"] != section:
            groups.append({"section": section, "lines": [], "subtotal": ZERO})
        groups[-1]["lines"].append(line)
        groups[-1]["subtotal"] += line.line_subtotal
    for group in groups:
        group["subtotal"] = round2(group["subtotal"])
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


class Quote(TotalsDocument, TimeStampedModel):
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


class SalesOrder(TotalsDocument, TimeStampedModel):
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
        lines = list(self.lines.all())
        if not lines:
            return False
        return all(line.qty_delivered >= line.qty for line in lines)

    @property
    def delivery_state(self):
        if self.status == self.STATUS_DELIVERED:
            return "delivered"
        lines = list(self.lines.all())
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
