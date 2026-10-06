from decimal import Decimal

from django import forms

from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm, BootstrapFormMixin, active_units, active_vat_rates

from .models import Category, KitComponent, Product


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
            "supplier_lead_days",
            "is_stock_tracked",
            "min_stock",
            "is_kit",
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
    """Form ridotto per creare un articolo al volo mentre si compila un documento.

    L'IVA di vendita e di acquisto è fissata al 22% standard (si corregge poi
    dalla scheda articolo, se serve).
    """

    main_supplier = forms.ModelChoiceField(
        label="Fornitore",
        queryset=Contact.objects.none(),
        required=False,
    )
    min_stock = forms.DecimalField(
        label="Riordino automatico (scorta minima)",
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=3,
        initial=0,
        help_text="Se la giacenza scende sotto questo valore l'articolo viene segnalato da riordinare.",
    )

    class Meta:
        model = Product
        fields = ["name", "uom", "main_supplier", "min_stock", "sale_price", "purchase_price"]
        labels = {
            "name": "Descrizione",
            "uom": "Unità di misura",
            "sale_price": "Prezzo vendita",
            "purchase_price": "Prezzo acquisto",
        }

    def __init__(self, *args, **kwargs):
        context_type = kwargs.pop("context_type", "sale")
        super().__init__(*args, **kwargs)
        self.fields["uom"].queryset = active_units()
        self.fields["main_supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["sale_price"].required = False
        self.fields["purchase_price"].required = False
        if context_type == "purchase":
            self.fields["sale_price"].widget.attrs["placeholder"] = "—"

    def save(self, commit=True):
        prodotto = super().save(commit=False)
        iva_standard = (
            active_vat_rates().filter(code="22").first()
            or active_vat_rates().first()
        )
        if iva_standard is not None:
            prodotto.sale_vat = iva_standard
            prodotto.purchase_vat = iva_standard
        if commit:
            prodotto.save()
            self.save_m2m()
        return prodotto


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
