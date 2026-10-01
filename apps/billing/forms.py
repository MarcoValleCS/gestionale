from django import forms

from apps.core.forms import BaseBootstrapModelForm, BootstrapFormMixin
from apps.sales.forms import CustomerChoiceFormMixin, LineFormMixin, PurchaseSupplierFormMixin

from .models import DeliveryNote, DeliveryNoteLine, PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, SalesInvoiceLine


class DeliveryNoteForm(CustomerChoiceFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = DeliveryNote
        fields = ["customer", "job", "date", "transport_reason", "carrier", "packages", "weight", "destination", "notes"]
        labels = {
            "transport_reason": "Causale trasporto",
            "packages": "Numero colli",
            "weight": "Peso (kg)",
            "destination": "Destinazione (se diversa dal cliente)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        self.apply_job_queryset()
        self.fields["job"].label = "Cantiere"


class DeliveryNoteLineForm(BaseBootstrapModelForm):
    """Riga DDT: solo articolo, descrizione, quantità e unità (senza prezzi)."""

    class Meta:
        model = DeliveryNoteLine
        fields = ["section", "product", "description", "qty", "uom"]

    def __init__(self, *args, **kwargs):
        from django.urls import reverse

        from apps.catalog.models import Product
        from apps.core.forms import active_units

        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(active=True).select_related("uom").order_by("name")
        self.fields["product"].required = False
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"
        self.fields["product"].widget.attrs["data-defaults-url"] = reverse("catalog:product_defaults", args=[0])
        self.fields["product"].widget.attrs["data-context"] = "sale"
        self.fields["product"].widget.attrs["class"] = "d-none"
        self.fields["product"].widget.attrs["data-autocomplete-target"] = "1"
        self.fields["uom"].queryset = active_units()
        self.fields["description"].required = False
        self.fields["description"].label = "Descrizione"

    def clean(self):
        data = super().clean()
        if not self.has_changed():
            return data
        product = data.get("product")
        description = (data.get("description") or "").strip()
        if product is not None:
            if not description:
                data["description"] = product.name
            if not data.get("uom"):
                data["uom"] = product.uom
        elif not description:
            raise forms.ValidationError("Indicare almeno l'articolo o la descrizione della riga.")
        return data


class SalesInvoiceForm(CustomerChoiceFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = SalesInvoice
        fields = ["customer", "job", "date", "due_date", "payment_term", "reference", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        self.apply_job_queryset()


class SalesInvoiceLineForm(LineFormMixin, BaseBootstrapModelForm):
    defaults_context = "sale"

    class Meta:
        model = SalesInvoiceLine
        fields = ["section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()


class PurchaseInvoiceForm(PurchaseSupplierFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = PurchaseInvoice
        fields = ["supplier", "job", "date", "due_date", "payment_term", "supplier_reference", "notes"]
        labels = {"supplier_reference": "Numero documento fornitore"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_supplier_queryset()
        from apps.jobs.models import Job

        self.fields["job"].queryset = Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name")
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].required = False


class PurchaseInvoiceLineForm(LineFormMixin, BaseBootstrapModelForm):
    defaults_context = "purchase"

    class Meta:
        model = PurchaseInvoiceLine
        fields = ["section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()


class ScanUploadForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(
        label="Foto o PDF del documento",
        help_text="Carica la scansione o la foto del DDT/fattura: il testo verrà letto automaticamente (OCR).",
    )
