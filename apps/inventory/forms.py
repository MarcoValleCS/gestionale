from django import forms

from apps.catalog.models import Product
from apps.core.forms import BootstrapFormMixin

from .models import Warehouse


class AdjustForm(BootstrapFormMixin, forms.Form):
    product = forms.ModelChoiceField(
        label="Articolo",
        queryset=Product.objects.filter(is_stock_tracked=True, active=True).select_related("uom").order_by("name"),
    )
    warehouse = forms.ModelChoiceField(label="Magazzino", queryset=Warehouse.objects.filter(active=True))
    new_quantity = forms.DecimalField(label="Nuova giacenza", max_digits=12, decimal_places=3, min_value=0)
    note = forms.CharField(label="Motivo della rettifica", max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].initial = Warehouse.get_default()
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"
