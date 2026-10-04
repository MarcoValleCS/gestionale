from django import forms

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, BootstrapFormMixin
from apps.sales.forms import LineFormMixin, PurchaseSupplierFormMixin

from .models import PriceListItem, PurchaseOrder, PurchaseOrderLine, SupplierPriceList


class SupplierPriceListForm(BaseBootstrapModelForm):
    class Meta:
        model = SupplierPriceList
        fields = ["supplier", "name", "valid_from", "valid_to", "notes", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["supplier"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["is_active"].initial = True


class PriceListItemForm(BaseBootstrapModelForm):
    class Meta:
        model = PriceListItem
        fields = ["product", "supplier_code", "price", "discount_pct", "min_qty", "note"]
        labels = {"supplier_code": "Codice fornitore"}

    def __init__(self, *args, **kwargs):
        from apps.core.forms import usa_autocomplete

        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(active=True).order_by("name")
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"
        # il menu dell'articolo porta solo la voce scelta: l'elenco lo cerca
        # l'autocompletamento (con migliaia di articoli non ci sta in pagina)
        self.fields["product"].widget.attrs["class"] = "d-none"
        self.fields["product"].widget.attrs["data-autocomplete-target"] = "1"
        usa_autocomplete(self.fields["product"])


class PriceListAdjustForm(BootstrapFormMixin, forms.Form):
    percent = forms.DecimalField(
        label="Variazione %",
        max_digits=7,
        decimal_places=2,
        initial="3",
        help_text="Es. 3 per aumentare tutti i prezzi del 3%, -5 per diminuirli del 5%.",
    )


class PurchaseOrderForm(PurchaseSupplierFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "job", "date", "expected_date", "payment_term", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_supplier_queryset()
        from apps.jobs.models import Job

        self.fields["job"].queryset = (
            Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED])
            .select_related("customer")
            .order_by("-created_at")
        )
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].required = False
        self.fields["job"].help_text = "Facoltativo: collega l'ordine al cantiere/commessa."


class PurchaseOrderLineForm(LineFormMixin, BaseBootstrapModelForm):
    defaults_context = "purchase"

    class Meta:
        model = PurchaseOrderLine
        fields = ["section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()
