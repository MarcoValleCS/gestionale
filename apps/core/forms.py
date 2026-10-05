"""Form condivisi: mixin Bootstrap e form di impostazione."""
from django import forms

from .models import Attachment, CompanySettings, PaymentTerm, Tag, UnitOfMeasure, VatRate


def active_units():
    return UnitOfMeasure.objects.filter(is_active=True)


def active_vat_rates():
    return VatRate.objects.filter(is_active=True)


def menu_unita():
    """Elenco delle unità di misura attive, pronto per i menu a tendina.

    Nei documenti ogni riga ha il suo menu: senza condivisione sarebbero una
    query per riga. L'elenco si rinnova al salvataggio di un'unità di misura
    (vedi i segnali in ``apps.core.models``).
    """
    from .cache import memoizza

    return memoizza("menu_unita", lambda: [("", "---------")] + [(u.pk, str(u)) for u in active_units()], 300)


def menu_aliquote():
    """Elenco delle aliquote IVA attive, pronto per i menu a tendina."""
    from .cache import memoizza

    return memoizza("menu_aliquote", lambda: [("", "---------")] + [(v.pk, str(v)) for v in active_vat_rates()], 300)


def active_payment_terms():
    return PaymentTerm.objects.all()


def all_tags():
    return Tag.objects.all()


class AutocompleteSelect(forms.Select):
    """Menu a tendina che rende solo l'opzione già scelta.

    I campi con autocompletamento (articolo, cliente, fornitore) usano un menu
    nascosto per portare l'identificativo della voce scelta: senza questo widget
    il browser scaricherebbe tutto l'archivio dentro ogni riga del documento
    (con migliaia di articoli sono megabyte di pagina). Le voci mancanti le
    aggiunge lo script di autocompletamento quando si sceglie.
    """

    def optgroups(self, name, value, attrs=None):
        # ``value`` arriva come stringa (per i menu a scelta singola) o come
        # elenco (scelta multipla): si normalizza in un elenco di identificativi.
        if value in (None, ""):
            scelti = []
        elif isinstance(value, (list, tuple, set)):
            scelti = [str(v) for v in value if v not in (None, "")]
        else:
            scelti = [str(value)]

        # Si rende solo la voce scelta (o nessuna, per una riga nuova): l'elenco
        # completo lo aggiunge l'autocompletamento quando si cerca.
        try:
            iteratore = self.choices
            queryset = iteratore.queryset.filter(pk__in=scelti)
            campo = getattr(iteratore, "field", None)
            self.choices = [
                (str(oggetto.pk), campo.label_from_instance(oggetto) if campo else str(oggetto))
                for oggetto in queryset
            ]
        except AttributeError:
            pass
        return super().optgroups(name, value, attrs)


def usa_autocomplete(campo):
    """Fa rendere al menu solo la voce scelta: le altre le aggiunge lo script.

    Serve sui campi con autocompletamento, dove il menu è nascosto e serve solo
    a portare l'identificativo. Le voci del campo vanno portate sul nuovo menu,
    altrimenti resterebbe vuoto e il valore scelto andrebbe perso.
    """
    widget = campo.widget
    if not isinstance(widget, AutocompleteSelect):
        nuovo = AutocompleteSelect(attrs=widget.attrs)
        nuovo.choices = widget.choices
        campo.widget = nuovo
    return campo


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
            "pec",
            "fiscal_regime",
            "address",
            "zip_code",
            "city",
            "province",
            "country",
            "email",
            "phone",
            "website",
            "iban",
            "logo",
            "app_logo",
            "document_color",
            "document_style",
            "theme_color",
            "theme_background",
            "quote_footer",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("document_color", "theme_color"):
            self.fields[campo].widget.attrs["type"] = "color"
            self.fields[campo].widget.attrs["class"] = "form-control form-control-color"
        self.fields["quote_footer"].widget.attrs["rows"] = 4


class WikiPageForm(BaseBootstrapModelForm):
    """Modifica di una pagina della guida."""

    class Meta:
        from .models import WikiPage as _WikiPage

        model = _WikiPage
        fields = ["title", "area", "summary", "body", "roles", "order", "is_published"]
        labels = {
            "title": "Titolo",
            "area": "Sezione",
            "summary": "Sommario (una riga)",
            "body": "Contenuto",
            "roles": "Ruoli che possono leggerla",
            "order": "Ordine nella sezione",
            "is_published": "Pubblicata",
        }
        help_texts = {
            "area": "Le pagine con la stessa sezione stanno insieme (es. Vendite, Magazzino, Impostazioni).",
            "roles": "Vuoto = tutti. Altrimenti: Vendite, Acquisti, Magazzino, Personale, Collaboratore, Amministratore.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs["rows"] = 16
        self.fields["summary"].widget.attrs["placeholder"] = "Es. Come preparare e inviare un preventivo al cliente."
        self.fields["area"].widget.attrs["list"] = "aree-guida"
        self.fields["roles"].widget.attrs["placeholder"] = "Es. Vendite, Amministratore"


class AttachmentForm(BaseBootstrapModelForm):
    class Meta:
        model = Attachment
        fields = ["file", "name", "notes"]
        labels = {"file": "File", "name": "Nome (facoltativo)", "notes": "Note"}
        help_texts = {"name": "Se vuoto viene usato il nome del file."}
