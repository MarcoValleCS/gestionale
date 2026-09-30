from django import forms

from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, active_units, active_vat_rates

from .models import Category, Product


class ProductForm(BaseBootstrapModelForm):
    class Meta:
        model = Product
        fields = [
            "code",
            "name",
            "description",
            "category",
            "uom",
            "barcode",
            "sale_price",
            "sale_vat",
            "purchase_price",
            "purchase_vat",
            "main_supplier",
            "is_stock_tracked",
            "min_stock",
            "tags",
            "notes",
            "active",
        ]
        widgets = {
            "tags": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["uom"].queryset = active_units()
        self.fields["sale_vat"].queryset = active_vat_rates()
        self.fields["purchase_vat"].queryset = active_vat_rates()
        self.fields["main_supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["main_supplier"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["code"].help_text = "Lasciare vuoto per generarlo automaticamente."
        self.fields["tags"].help_text = "Tieni premuto Ctrl per selezionare più etichette."
        if not self.instance.pk:
            default_sale = active_vat_rates().filter(is_default_sales=True).first()
            default_purchase = active_vat_rates().filter(is_default_purchase=True).first()
            if default_sale:
                self.fields["sale_vat"].initial = default_sale
            if default_purchase:
                self.fields["purchase_vat"].initial = default_purchase


class CategoryForm(BaseBootstrapModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent", "notes"]
