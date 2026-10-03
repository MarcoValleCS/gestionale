"""DDT (documenti di trasporto), fatture emesse e ricevute."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.contacts.models import Contact
from apps.core.models import NumberSequence, PaymentTerm, TimeStampedModel
from apps.sales.models import DocumentLine, SalesOrder, TotalsDocument


class DeliveryNote(TimeStampedModel):
    """DDT in uscita (vendita): accompagna la merce verso il cliente."""

    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_ISSUED, "Emesso"),
        (STATUS_CANCELLED, "Annullato"),
    ]

    number = models.CharField("Numero", max_length=30, unique=True, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="delivery_notes", verbose_name="Cliente")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_notes", verbose_name="Cantiere"
    )
    source_order = models.ForeignKey(
        SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_notes", verbose_name="Da ordine cliente"
    )
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issued_at = models.DateTimeField("Emesso il", null=True, blank=True)
    invoiced = models.BooleanField("Fatturato", default=False)
    transport_reason = models.CharField("Causale trasporto", max_length=100, blank=True, default="Vendita")
    carrier = models.CharField("Vettore", max_length=100, blank=True)
    packages = models.PositiveIntegerField("N. colli", null=True, blank=True)
    weight = models.DecimalField("Peso (kg)", max_digits=10, decimal_places=3, null=True, blank=True)
    destination = models.TextField("Destinazione", blank=True, help_text="Se vuoto usa l'indirizzo del cantiere o del cliente.")
    notes = models.TextField("Note", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_notes", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "DDT"
        verbose_name_plural = "DDT"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="ddt_status_date_idx"),
            models.Index(fields=["customer", "-date"], name="ddt_customer_date_idx"),
        ]

    def __str__(self):
        return f"DDT {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_DELIVERY_NOTE).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status == self.STATUS_DRAFT

    @property
    def total_qty(self):
        return sum((line.qty for line in self.lines.all()), Decimal("0"))

    @property
    def destination_address(self):
        if self.destination:
            return self.destination
        if self.job_id and self.job.full_address:
            return self.job.full_address
        return self.customer.address


class DeliveryNoteLine(DocumentLine):
    delivery_note = models.ForeignKey(DeliveryNote, on_delete=models.CASCADE, related_name="lines", verbose_name="DDT")
    source_order_line = models.ForeignKey(
        "sales.SalesOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_note_lines",
        verbose_name="Riga ordine collegata",
    )


class SalesInvoice(TotalsDocument, TimeStampedModel):
    """Fattura emessa al cliente (documento interno/cortesia, pronta per l'SDI)."""

    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_SENT = "sent"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_ISSUED, "Emessa"),
        (STATUS_SENT, "Inviata"),
        (STATUS_PAID, "Pagata"),
        (STATUS_CANCELLED, "Annullata"),
    ]

    number = models.CharField("Numero", max_length=30, unique=True, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    due_date = models.DateField("Scadenza pagamento", null=True, blank=True)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="sales_invoices", verbose_name="Cliente")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_invoices", verbose_name="Cantiere"
    )
    source_order = models.ForeignKey(
        SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_invoices", verbose_name="Da ordine cliente"
    )
    source_delivery_note = models.ForeignKey(
        DeliveryNote, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_invoices", verbose_name="Da DDT"
    )
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    reference = models.CharField("Vostro riferimento", max_length=100, blank=True)
    notes = models.TextField("Note", blank=True)
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issued_at = models.DateTimeField("Emessa il", null=True, blank=True)
    sent_at = models.DateTimeField("Inviata il", null=True, blank=True)
    paid_at = models.DateTimeField("Pagata il", null=True, blank=True)

    # Fatturazione elettronica
    SDI_NOT_SENT = "not_sent"
    SDI_GENERATED = "generated"
    SDI_SENT = "sent"
    SDI_DELIVERED = "delivered"
    SDI_ACCEPTED = "accepted"
    SDI_REJECTED = "rejected"
    SDI_FAILED = "failed"
    SDI_STATUS_CHOICES = [
        (SDI_NOT_SENT, "Non inviata"),
        (SDI_GENERATED, "XML generato"),
        (SDI_SENT, "Inviata allo SDI"),
        (SDI_DELIVERED, "Consegnata"),
        (SDI_ACCEPTED, "Accettata"),
        (SDI_REJECTED, "Scartata"),
        (SDI_FAILED, "Mancata consegna"),
    ]
    xml_file = models.FileField("File XML (FatturaPA)", upload_to="sdi/%Y/", blank=True)
    sdi_status = models.CharField("Stato SDI", max_length=20, choices=SDI_STATUS_CHOICES, default=SDI_NOT_SENT)
    sdi_sent_at = models.DateTimeField("Inviata allo SDI il", null=True, blank=True)
    sdi_note = models.CharField("Esito / nota SDI", max_length=300, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_invoices", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Fattura emessa"
        verbose_name_plural = "Fatture emesse"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="sinv_status_date_idx"),
            models.Index(fields=["customer", "-date"], name="sinv_customer_date_idx"),
            # lo scadenzario cerca le fatture aperte per scadenza
            models.Index(fields=["status", "due_date"], name="sinv_due_idx"),
        ]

    def __str__(self):
        return f"Fattura {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_SALES_INVOICE).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_open(self):
        return self.status in {self.STATUS_ISSUED, self.STATUS_SENT}

    @property
    def is_overdue(self):
        return bool(self.is_open and self.due_date and self.due_date < timezone.localdate())


class SalesInvoiceLine(DocumentLine):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines", verbose_name="Fattura")


class PurchaseInvoice(TotalsDocument, TimeStampedModel):
    """Fattura ricevuta dal fornitore."""

    STATUS_DRAFT = "draft"
    STATUS_REGISTERED = "registered"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Bozza"),
        (STATUS_REGISTERED, "Da pagare"),
        (STATUS_PAID, "Pagata"),
        (STATUS_CANCELLED, "Annullata"),
    ]

    number = models.CharField("Numero interno", max_length=30, unique=True, blank=True)
    supplier_reference = models.CharField("Numero documento fornitore", max_length=50, blank=True)
    date = models.DateField("Data", default=timezone.localdate)
    due_date = models.DateField("Scadenza pagamento", null=True, blank=True)
    supplier = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="purchase_invoices", verbose_name="Fornitore")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_invoices", verbose_name="Cantiere"
    )
    source_po = models.ForeignKey(
        "purchasing.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_invoices",
        verbose_name="Da ordine fornitore",
    )
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Condizione di pagamento"
    )
    notes = models.TextField("Note", blank=True)
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    registered_at = models.DateTimeField("Registrata il", null=True, blank=True)
    paid_at = models.DateTimeField("Pagata il", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_invoices", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Fattura ricevuta"
        verbose_name_plural = "Fatture ricevute"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-date"], name="pinv_status_date_idx"),
            models.Index(fields=["supplier", "-date"], name="pinv_supplier_date_idx"),
            models.Index(fields=["status", "due_date"], name="pinv_due_idx"),
        ]

    def __str__(self):
        return f"Fattura ricevuta {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = NumberSequence.get_for(NumberSequence.DOC_TYPE_PURCHASE_INVOICE).take_next_number()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_open(self):
        return self.status == self.STATUS_REGISTERED


class PurchaseInvoiceLine(DocumentLine):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="lines", verbose_name="Fattura")

