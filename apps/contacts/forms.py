from django import forms

from apps.core.forms import BaseBootstrapModelForm

from .models import Contact


class ContactForm(BaseBootstrapModelForm):
    class Meta:
        model = Contact
        fields = [
            "name",
            "is_customer",
            "is_supplier",
            "vat_number",
            "tax_code",
            "sdi_code",
            "pec",
            "email",
            "phone",
            "mobile",
            "website",
            "address",
            "zip_code",
            "city",
            "province",
            "country",
            "payment_term",
            "tags",
            "notes",
            "active",
        ]
        widgets = {
            "tags": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].help_text = "Tieni premuto Ctrl per selezionare più etichette."
