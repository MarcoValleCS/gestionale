"""Form condivisi: mixin Bootstrap e form di impostazione."""
from django import forms

from .models import CompanySettings, PaymentTerm, Tag, UnitOfMeasure, VatRate


def active_units():
    return UnitOfMeasure.objects.filter(is_active=True)


def active_vat_rates():
    return VatRate.objects.filter(is_active=True)


def active_payment_terms():
    return PaymentTerm.objects.all()


def all_tags():
    return Tag.objects.all()


class BootstrapFormMixin:
    """Aggiunge le classi Bootstrap ai widget dei form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 3)
            if type(widget) is forms.DateInput:
                widget.attrs.setdefault("type", "date")
            if type(widget) is forms.NumberInput:
                widget.attrs.setdefault("step", "any")


class BaseBootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    pass


class UnitOfMeasureForm(BaseBootstrapModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ["code", "name", "is_active"]


class VatRateForm(BaseBootstrapModelForm):
    class Meta:
        model = VatRate
        fields = ["code", "name", "rate", "nature", "is_default_sales", "is_default_purchase", "is_active"]


class TagForm(BaseBootstrapModelForm):
    class Meta:
        model = Tag
        fields = ["name", "color", "description"]


class PaymentTermForm(BaseBootstrapModelForm):
    class Meta:
        model = PaymentTerm
        fields = ["name", "days", "end_of_month", "notes"]


class CompanySettingsForm(BaseBootstrapModelForm):
    class Meta:
        model = CompanySettings
        fields = [
            "name",
            "vat_number",
            "tax_code",
            "address",
            "zip_code",
            "city",
            "province",
            "country",
            "email",
            "phone",
            "website",
            "iban",
            "quote_footer",
        ]
