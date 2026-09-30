from django import forms

from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, BootstrapFormMixin, active_units, active_vat_rates

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


class ProductQuickForm(BaseBootstrapModelForm):
    """Form ridotto per creare un articolo al volo mentre si compila un documento."""

    class Meta:
        model = Product
        fields = ["name", "uom", "sale_price", "sale_vat", "purchase_price", "purchase_vat"]
        labels = {
            "name": "Descrizione",
            "uom": "Unità di misura",
            "sale_price": "Prezzo vendita",
            "sale_vat": "IVA vendita",
            "purchase_price": "Prezzo acquisto",
            "purchase_vat": "IVA acquisto",
        }

    def __init__(self, *args, **kwargs):
        context_type = kwargs.pop("context_type", "sale")
        super().__init__(*args, **kwargs)
        self.fields["uom"].queryset = active_units()
        self.fields["sale_vat"].queryset = active_vat_rates()
        self.fields["purchase_vat"].queryset = active_vat_rates()
        default_sale = active_vat_rates().filter(is_default_sales=True).first()
        default_purchase = active_vat_rates().filter(is_default_purchase=True).first()
        if not self.instance.pk:
            self.fields["sale_vat"].initial = default_sale
            self.fields["purchase_vat"].initial = default_purchase
            if context_type == "purchase":
                self.fields["sale_price"].widget.attrs["placeholder"] = "—"
        self.fields["sale_price"].required = False
        self.fields["purchase_price"].required = False


class ProductImportForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(
        label="File CSV o Excel",
        help_text="Formati supportati: .csv (separatore ; o ,) e .xlsx.",
    )
    supplier = forms.ModelChoiceField(
        label="Fornitore predefinito",
        queryset=Contact.objects.none(),
        required=False,
        help_text="Usato per gli articoli che non hanno la colonna «fornitore».",
    )
    update_pricelist = forms.BooleanField(
        label="Aggiorna il listino del fornitore con il prezzo di acquisto",
        required=False,
        initial=True,
        help_text="Crea o aggiorna le voci di listino per gli articoli importati con un prezzo di acquisto.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["supplier"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
