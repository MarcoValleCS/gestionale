from datetime import timedelta

from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, active_units, active_vat_rates
from apps.core.models import CompanySettings

from .models import Quote, QuoteLine, SalesOrder, SalesOrderLine


class CustomerChoiceFormMixin:
    def apply_customer_queryset(self):
        self.fields["customer"].queryset = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        self.fields["customer"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"


class LineFormMixin:
    defaults_context = "sale"

    def apply_line_fields(self):
        self.fields["product"].queryset = Product.objects.filter(active=True).select_related("uom").order_by("name")
        self.fields["product"].required = False
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"
        self.fields["product"].widget.attrs["data-defaults-url"] = reverse("catalog:product_defaults", args=[0])
        self.fields["product"].widget.attrs["data-context"] = self.defaults_context
        self.fields["uom"].queryset = active_units()
        self.fields["vat_rate"].queryset = active_vat_rates()
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


class QuoteForm(CustomerChoiceFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = Quote
        fields = ["customer", "date", "valid_until", "payment_term", "reference", "terms_text", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
            self.fields["valid_until"].initial = timezone.localdate() + timedelta(days=30)
            self.fields["terms_text"].initial = CompanySettings.load().quote_footer


class SalesOrderForm(CustomerChoiceFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer", "date", "expected_date", "payment_term", "reference", "terms_text", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
            self.fields["terms_text"].initial = CompanySettings.load().quote_footer


class QuoteLineForm(LineFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = QuoteLine
        fields = ["product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()


class SalesOrderLineForm(LineFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = SalesOrderLine
        fields = ["product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()
