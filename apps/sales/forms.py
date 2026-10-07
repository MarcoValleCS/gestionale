from datetime import timedelta

from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Product
from apps.contacts.models import Contact
from apps.core.forms import AutocompleteSelect, BaseBootstrapModelForm, menu_aliquote, menu_unita, usa_autocomplete
from apps.core.models import CompanySettings

from .models import (
    DISPLAY_LINE_TYPES,
    Quote,
    QuoteLine,
    QuoteTemplate,
    QuoteTemplateLine,
    SalesOrder,
    SalesOrderLine,
)


class CustomerChoiceFormMixin:
    def apply_customer_queryset(self):
        self.fields["customer"].queryset = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        self.fields["customer"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["customer"].widget.attrs["class"] = "d-none"
        self.fields["customer"].widget.attrs["data-autocomplete-target"] = "1"
        usa_autocomplete(self.fields["customer"])

    def apply_job_queryset(self):
        from apps.jobs.models import Job

        self.fields["job"].queryset = (
            Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED])
            .select_related("customer")
            .order_by("-created_at")
        )
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].required = False
        self.fields["job"].help_text = "Facoltativo: collega il documento al cantiere/commessa."

    def apply_commission_queryset(self):
        """Chi percepisce la provvigione può essere chiunque: non solo un cliente."""
        self.fields["commission_contact"].queryset = Contact.objects.filter(active=True).order_by("name")
        self.fields["commission_contact"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["commission_contact"].required = False
        self.fields["commission_contact"].help_text = "Facoltativo: chi ha presentato il cliente."
        self.fields["commission_pct"].required = False
        self.fields["commission_pct"].help_text = "Percentuale sull'imponibile. 0 = nessuna provvigione."

    def clean_terms_text(self):
        """Ripulisce le note formattate prima di salvarle.

        Il campo esiste solo sui documenti di vendita: Django chiama questo
        metodo solo se il form ha davvero il campo «terms_text».
        """
        from apps.core.richtext import clean_notes

        return clean_notes(self.cleaned_data.get("terms_text"))


class PurchaseSupplierFormMixin:
    def apply_supplier_queryset(self):
        self.fields["supplier"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["supplier"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["supplier"].widget.attrs["class"] = "d-none"
        self.fields["supplier"].widget.attrs["data-autocomplete-target"] = "1"
        usa_autocomplete(self.fields["supplier"])


class LineFormMixin:
    defaults_context = "sale"

    # Campi di servizio del modulo righe: cambiarli da soli non rende
    # «compilata» la riga vuota in fondo al modulo, che il JavaScript rinumera
    # comunque. Senza questo, il salvataggio del preventivo fallisce senza che
    # l'utente veda nulla.
    service_fields = {"position", "line_type"}

    def has_changed(self):
        if not super().has_changed():
            return False
        ignorati = set(self.service_fields)
        if "line_type" in self.fields:
            # Preventivi, ordini e modelli: anche la vecchia sezione è nascosta
            ignorati.add("section")
        return any(name not in ignorati for name in self.changed_data)

    def apply_line_fields(self):
        self.fields["product"].queryset = Product.objects.filter(active=True).select_related("uom").order_by("name")
        self.fields["product"].required = False
        self.fields["product"].label_from_instance = lambda obj: f"{obj.code} – {obj.name}"
        self.fields["product"].widget.attrs["data-defaults-url"] = reverse("catalog:product_defaults", args=[0])
        self.fields["product"].widget.attrs["data-context"] = self.defaults_context
        self.fields["product"].widget.attrs["class"] = "d-none"
        self.fields["product"].widget.attrs["data-autocomplete-target"] = "1"
        # Il menu dell'articolo porta solo la voce scelta: l'elenco completo lo
        # aggiunge l'autocompletamento. Senza questo, ogni riga scaricherebbe
        # tutto il catalogo.
        usa_autocomplete(self.fields["product"])
        # Se la riga esiste già, il suo articolo è stato caricato insieme alle
        # righe del documento: si usa quello, senza una query per riga. Sui
        # moduli inviati si lascia invece al campo il compito di leggere il
        # valore ricevuto.
        if not self.is_bound:
            prodotto = getattr(self.instance, "product", None)
            if prodotto is not None:
                self.fields["product"].widget.choices = [
                    (str(prodotto.pk), self.fields["product"].label_from_instance(prodotto))
                ]
        self.fields["uom"].choices = menu_unita()
        self.fields["vat_rate"].choices = menu_aliquote()
        self.fields["description"].required = False
        self.fields["description"].label = "Descrizione"
        if "line_type" in self.fields:
            # Preventivi, ordini e modelli: posizione e tipo riga viaggiano
            # nascosti (l'ordine lo decide l'utente con le frecce su/giù) e la
            # vecchia sezione per riga lascia il posto alle righe «Sezione».
            self.fields["position"].required = False
            self.fields["position"].widget = forms.HiddenInput()
            self.fields["line_type"].required = False
            self.fields["line_type"].widget = forms.HiddenInput()
            self.fields["section"].required = False
            self.fields["section"].widget = forms.HiddenInput()
        else:
            # Fatture e DDT: la sezione resta il campo di testo per riga
            self.fields["section"].required = False
            self.fields["section"].widget.attrs["placeholder"] = "es. Bagno 1"

    def clean(self):
        data = super().clean()
        if not self.has_changed():
            return data
        if data.get("line_type") in DISPLAY_LINE_TYPES:
            # sezione, sottosezione o nota: serve solo il testo
            if not (data.get("description") or "").strip():
                raise forms.ValidationError("Scrivi il testo della sezione, della sottosezione o della nota.")
            data["product"] = None
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
        fields = [
            "customer",
            "job",
            "date",
            "valid_until",
            "payment_term",
            "reference",
            "commission_contact",
            "commission_pct",
            "terms_text",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        self.apply_job_queryset()
        self.apply_commission_queryset()
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
            self.fields["valid_until"].initial = timezone.localdate() + timedelta(days=30)
            self.fields["terms_text"].initial = CompanySettings.load().quote_footer


class SalesOrderForm(CustomerChoiceFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = SalesOrder
        fields = [
            "customer",
            "job",
            "date",
            "expected_date",
            "payment_term",
            "reference",
            "commission_contact",
            "commission_pct",
            "terms_text",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_customer_queryset()
        self.apply_job_queryset()
        self.apply_commission_queryset()
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
            self.fields["terms_text"].initial = CompanySettings.load().quote_footer


class QuoteTemplateForm(BaseBootstrapModelForm):
    class Meta:
        model = QuoteTemplate
        fields = ["name", "description", "payment_term", "terms_text", "notes", "sort_order", "is_active"]


class QuoteTemplateLineForm(LineFormMixin, BaseBootstrapModelForm):
    defaults_context = "sale"

    class Meta:
        model = QuoteTemplateLine
        fields = ["position", "line_type", "section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()


class QuoteLineForm(LineFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = QuoteLine
        fields = ["position", "line_type", "section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()


class SalesOrderLineForm(LineFormMixin, BaseBootstrapModelForm):
    class Meta:
        model = SalesOrderLine
        fields = ["position", "line_type", "section", "product", "description", "qty", "uom", "unit_price", "discount_pct", "vat_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_line_fields()
