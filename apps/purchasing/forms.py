from django import forms

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, BootstrapFormMixin
from apps.sales.forms import LineFormMixin

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
        fields = ["product", "price", "discount_pct", "min_qty", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(active=True).order_by("name")
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"


class PriceListAdjustForm(BootstrapFormMixin, forms.Form):
    percent = forms.DecimalField(
        label="Variazione %",
        max_digits=7,
        decimal_places=2,
        initial="3",
        help_text="Es. 3 per aumentare tutti i prezzi del 3%, -5 per diminuirli del 5%.",
    )


class PurchaseOrderForm(BaseBootstrapModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "date", "expected_date", "payment_term", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["supplier"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"


class PurchaseOrderLineForm(LineFormMixin, BaseBootstrapModelForm):
    defaults_context = "purchase"

    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()
