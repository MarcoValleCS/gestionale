"""Ordini fornitore e listini."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.models import NumberSequence, PaymentTerm, TimeStampedModel
from apps.sales.models import DocumentLine, SalesOrder, TotalsDocument, round3

ZERO = Decimal("0")
FOUR_PLACES = Decimal("0.0001")


def round4(value):
    """Arrotondamento commerciale a quattro decimali (prezzi unitari)."""
    return Decimal(value or 0).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


class SupplierPriceList(TimeStampedModel):
    supplier = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="price_lists", verbose_name="Fornitore")
    name = models.CharField("Nome listino", max_length=120)
    valid_from = models.DateField("Valido dal", default=timezone.localdate)
    valid_to = models.DateField("Valido fino al", null=True, blank=True)
    notes = models.TextField("Note", blank=True)
    is_active = models.BooleanField("Attivo", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="price_lists", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Listino fornitore"
        verbose_name_plural = "Listini fornitori"
        ordering = ["supplier__name", "-valid_from", "name"]

    def __str__(self):
        return f"{self.supplier.name} – {self.name}"

    @property
    def is_current(self):
        today = timezone.localdate()
        if not self.is_active or self.valid_from > today:
            return False
        return self.valid_to is None or self.valid_to >= today

    def product_price(self, product):
        item = self.items.filter(product=product).first()
        return item.effective_price if item else None


class PriceListItem(TimeStampedModel):
    pricelist = models.ForeignKey(SupplierPriceList, on_delete=models.CASCADE, related_name="items", verbose_name="Listino")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_list_items", verbose_name="Articolo")
    price = models.DecimalField("Prezzo", max_digits=12, decimal_places=4, default=ZERO)
    discount_pct = models.DecimalField("Sconto %", max_digits=5, decimal_places=2, default=ZERO)
    min_qty = models.DecimalField("Quantità minima", max_digits=12, decimal_places=3, default=Decimal("1"))
    note = models.CharField("Note", max_length=200, blank=True)

    class Meta:
        verbose_name = "Voce di listino"
        verbose_name_plural = "Voci di listino"
        constraints = [models.UniqueConstraint(fields=["pricelist", "product"], name="unique_product_per_pricelist")]
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product} – {self.effective_price} €"

    @property
    def effective_price(self):
        price = Decimal(self.price or 0)
        discount = Decimal(self.discount_pct or 0)
        return round4(price * (1 - discount / 100))


class PriceListAdjustment(models.Model):
    """Storico delle variazioni percentuali applicate a un listino."""

    pricelist = models.ForeignKey(SupplierPriceList, on_delete=models.CASCADE, related_name="adjustments", verbose_name="Listino")
    percent = models.DecimalField("Variazione %", max_digits=7, decimal_places=2)
    items_count = models.PositiveIntegerField("Articoli aggiornati", default=0)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="price_adjustments", verbose_name="Applicata da"
    )
    applied_at = models.DateTimeField("Applicata il", auto_now_add=True)

    class Meta:
        verbose_name = "Variazione listino"
        verbose_name_plural = "Variazioni listino"
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.pricelist} {self.percent:+}%"


class PurchaseOrder(TotalsDocument, TimeStampedModel):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PARTIAL = "received_partial"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_SENT, "Inviato"),
        (STATUS_CONFIRMED, "Confermato"),
        (STATUS_PARTIAL, "Parzialmente ricevuto"),
        (STATUS_RECEIVED, "Ricevuto"),
        (STATUS_CANCELLED, "Annullato"),
    ]

    number = models.CharField("Numero", max_length=30, unique=True, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    expected_date = models.DateField("Consegna prevista", null=True, blank=True)
    supplier = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="purchase_orders", verbose_name="Fornitore")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders", verbose_name="Cantiere"
    )
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    source_sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
        verbose_name="Da ordine cliente",
    )
    notes = models.TextField("Note", blank=True)
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Ordine fornitore"
        verbose_name_plural = "Ordini fornitore"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="po_status_date_idx"),
            models.Index(fields=["supplier", "-date"], name="po_supplier_date_idx"),
        ]

    def __str__(self):
        return self.number or f"Ordine fornitore {self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_PURCHASE_ORDER).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status in {self.STATUS_DRAFT, self.STATUS_SENT}

    @property
    def can_receive(self):
        return self.status in {self.STATUS_DRAFT, self.STATUS_SENT, self.STATUS_CONFIRMED, self.STATUS_PARTIAL}

    @property
    def all_received(self):
        lines = list(self.lines.all())
        if not lines:
            return False
        return all(line.qty_received >= line.qty for line in lines)


class PurchaseOrderLine(DocumentLine):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines", verbose_name="Ordine fornitore")
    qty_received = models.DecimalField("Quantità ricevuta", max_digits=12, decimal_places=3, default=ZERO)

    @property
    def qty_remaining(self):
        return round3(Decimal(self.qty or 0) - Decimal(self.qty_received or 0))

    @property
    def unit_cost(self):
        price = Decimal(self.unit_price or 0)
        discount = Decimal(self.discount_pct or 0)
        return round4(price * (1 - discount / 100))
