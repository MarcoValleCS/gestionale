"""Form condivisi: mixin Bootstrap e form di impostazione."""
from decimal import Decimal, InvalidOperation

from django import forms

from .models import Attachment, CompanySettings, PaymentTerm, Tag, UnitOfMeasure, VatRate
from .rounding import round2


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


class PriceInput(forms.NumberInput):
    """Campo prezzo con due decimali.

    Nel database i prezzi restano con quattro decimali (i listini fornitore
    generano sconti con più cifre), ma chi compila un documento ragiona in
    centesimi: «12,3400» in una riga confonde e allunga la tabella. Il valore
    resta un numero, si arrotonda solo per la visualizzazione.
    """

    def format_value(self, value):
        if value in (None, ""):
            return ""
        try:
            numero = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return super().format_value(value)
        return f"{round2(numero):.2f}"


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
            "sales_terms",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("document_color", "theme_color"):
            self.fields[campo].widget.attrs["type"] = "color"
            self.fields[campo].widget.attrs["class"] = "form-control form-control-color"
        self.fields["quote_footer"].widget.attrs["rows"] = 4
        self.fields["sales_terms"].widget.attrs["rows"] = 12


class NotePredefiniteForm(BaseBootstrapModelForm):
    """Testo proposto nelle note dei nuovi documenti."""

    class Meta:
        model = CompanySettings
        fields = ["note_vendita", "note_acquisto"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note_acquisto"].widget.attrs["rows"] = 5

    def clean_note_vendita(self):
        from .richtext import clean_notes

        return clean_notes(self.cleaned_data.get("note_vendita"))


class EmailInvioForm(BaseBootstrapModelForm):
    """Casella da cui partono le email di chi non ha una casella personale."""

    password = forms.CharField(
        label="Password della casella",
        required=False,
        strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Lascia vuoto per tenere quella già salvata. Viene salvata cifrata.",
    )
    rimuovi_password = forms.BooleanField(label="Cancella la password salvata", required=False)

    class Meta:
        model = CompanySettings
        fields = [
            "mittente_nome",
            "mittente_email",
            "smtp_host",
            "smtp_porta",
            "smtp_sicurezza",
            "smtp_utente",
            "caselle_host",
            "caselle_sicurezza",
        ]

    def clean(self):
        from django.conf import settings

        cleaned = super().clean()
        email = (cleaned.get("mittente_email") or "").strip()
        if not email:
            return cleaned
        utente = (cleaned.get("smtp_utente") or email).strip().lower()
        nuova = cleaned.get("password") or ""
        salvata = "" if cleaned.get("rimuovi_password") else self.instance.password_smtp
        da_env = utente == (settings.EMAIL_HOST_USER or "").strip().lower() and settings.EMAIL_HOST_PASSWORD
        if not (nuova or salvata or da_env):
            self.add_error("password", "Inserisci la password della casella: senza, il server rifiuta l'invio.")
        return cleaned

    def save(self, commit=True):
        azienda = super().save(commit=False)
        if self.cleaned_data.get("rimuovi_password"):
            azienda.imposta_password_smtp("")
        if self.cleaned_data.get("password"):
            azienda.imposta_password_smtp(self.cleaned_data["password"])
        if commit:
            azienda.save()
        return azienda


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
