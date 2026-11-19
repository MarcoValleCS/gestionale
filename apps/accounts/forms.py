from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import Group

from apps.core.forms import BootstrapFormMixin

from .models import User
from .permissions import ALL_ROLES


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class CampiCasellaMixin:
    """Password della casella email personale: si scrive, non si rilegge.

    Lasciata vuota resta quella salvata; «Cancella» la toglie e l'utente torna
    a spedire dalla casella aziendale.
    """

    def aggiungi_campi_casella(self):
        self.fields["password_casella"] = forms.CharField(
            label="Password della casella email",
            required=False,
            strip=False,
            widget=forms.PasswordInput(
                render_value=False, attrs={"autocomplete": "new-password", "class": "form-control"}
            ),
            help_text=(
                "La password della casella (es. quella di Aruba): serve a spedire dal gestionale con questa email. "
                "Lascia vuoto per tenere quella salvata. Viene salvata cifrata."
            ),
        )
        self.fields["rimuovi_password_casella"] = forms.BooleanField(
            label="Cancella la password salvata (le email partiranno dalla casella aziendale)",
            required=False,
            widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        )

    def controlla_casella(self, cleaned):
        if cleaned.get("password_casella") and not (cleaned.get("email") or "").strip():
            self.add_error("email", "Indica l'email della casella a cui appartiene la password.")
        return cleaned

    def applica_casella(self, utente):
        if self.cleaned_data.get("rimuovi_password_casella"):
            utente.imposta_password_casella("")
        if self.cleaned_data.get("password_casella"):
            utente.imposta_password_casella(self.cleaned_data["password_casella"])
        return utente


class CasellaPersonaleForm(CampiCasellaMixin, BootstrapFormMixin, forms.ModelForm):
    """La propria casella email: le email inviate dal gestionale partono da qui."""

    class Meta:
        model = User
        fields = ["email"]
        labels = {"email": "La tua email"}
        help_texts = {"email": "Es. simone@aquaforma.it. Con la password qui sotto le tue email partono da questa casella."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aggiungi_campi_casella()
        if not self.instance.password_email:
            del self.fields["rimuovi_password_casella"]

    def clean(self):
        return self.controlla_casella(super().clean())

    def save(self, commit=True):
        utente = self.applica_casella(super().save(commit=False))
        if not (utente.email or "").strip():
            utente.imposta_password_casella("")
        if commit:
            utente.save(update_fields=["email", "password_email"])
        return utente


def _valida_password(form, campo, password):
    """Applica alla password scelta dall'amministratore le stesse regole del
    cambio password (lunghezza, password comuni, solo numeri, simile al nome)."""
    utente = form.instance if form.instance.pk else User(
        username=form.cleaned_data.get("username") or "",
        first_name=form.cleaned_data.get("first_name") or "",
        last_name=form.cleaned_data.get("last_name") or "",
        email=form.cleaned_data.get("email") or "",
    )
    try:
        password_validation.validate_password(password, utente)
    except forms.ValidationError as errore:
        form.add_error(campo, errore)


class UserForm(CampiCasellaMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "groups", "is_active"]
        labels = {
            "username": "Nome utente",
            "first_name": "Nome",
            "last_name": "Cognome",
            "is_active": "Attivo",
            "groups": "Ruoli",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.filter(name__in=ALL_ROLES).order_by("name")
        self.fields["groups"].help_text = "I ruoli determinano le funzioni accessibili a questo utente."
        self.fields["groups"].required = True
        self.fields["is_active"].initial = True
        self.fields["email"].help_text = "Con la password della casella qui sotto, le email di questo utente partono dalla sua casella."
        self.aggiungi_campi_casella()
        if not self.instance.password_email:
            del self.fields["rimuovi_password_casella"]

    def clean(self):
        return self.controlla_casella(super().clean())


class UserCreateForm(UserForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=10)
    password2 = forms.CharField(label="Conferma password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Le due password non coincidono.")
        elif cleaned.get("password1"):
            _valida_password(self, "password1", cleaned["password1"])
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        self.applica_casella(user)
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(UserForm):
    new_password = forms.CharField(
        label="Nuova password",
        widget=forms.PasswordInput,
        required=False,
        min_length=10,
        help_text="Compilare solo per cambiare la password.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password"):
            _valida_password(self, "new_password", cleaned["new_password"])
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            user.set_password(password)
        self.applica_casella(user)
        if commit:
            user.save()
            self.save_m2m()
        return user
