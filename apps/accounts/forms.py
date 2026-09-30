from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import Group

from apps.core.forms import BootstrapFormMixin

from .models import User
from .permissions import ALL_ROLES


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class UserForm(BootstrapFormMixin, forms.ModelForm):
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


class UserCreateForm(UserForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label="Conferma password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Le due password non coincidono.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(UserForm):
    new_password = forms.CharField(
        label="Nuova password",
        widget=forms.PasswordInput,
        required=False,
        min_length=8,
        help_text="Compilare solo per cambiare la password.",
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user
