"""Form di dipendenti, registrazione ore e ferie/permessi."""
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import BaseBootstrapModelForm
from apps.jobs.models import Job

from .models import Collaborator, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry

MIN_HOURS = Decimal("0.25")


def active_employees():
    return Employee.objects.filter(active=True).order_by("last_name", "first_name")


def open_jobs():
    return Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).select_related("customer").order_by("name")


class EmployeeForm(BaseBootstrapModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name",
            "last_name",
            "fiscal_code",
            "email",
            "phone",
            "qualification",
            "user",
            "hired_on",
            "terminated_on",
            "contract_weekly_hours",
            "hourly_cost",
            "holiday_days_per_year",
            "rol_hours_per_year",
            "active",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["user"].label_from_instance = lambda obj: obj.get_full_name() or obj.username
        self.fields["user"].required = False
        self.fields["user"].help_text = "Facoltativo: collega il dipendente a un utente che accede al gestionale."
        self.fields["terminated_on"].help_text = "Lascia vuoto finché il rapporto è in corso."

    def clean(self):
        cleaned = super().clean()
        hired = cleaned.get("hired_on")
        terminated = cleaned.get("terminated_on")
        if hired and terminated and terminated < hired:
            self.add_error("terminated_on", "La data di cessazione non può precedere quella di assunzione.")
        return cleaned


class TimeEntryForm(BaseBootstrapModelForm):
    class Meta:
        model = TimeEntry
        fields = ["employee", "date", "hours", "kind", "job", "description", "billable"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = active_employees()
        self.fields["employee"].label_from_instance = lambda obj: f"{obj.full_name} ({obj.code})"
        self.fields["job"].queryset = open_jobs()
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].required = False
        self.fields["hours"].widget.attrs["step"] = "0.25"
        self.fields["hours"].widget.attrs["min"] = "0.25"
        self.fields["hours"].help_text = "In ore e frazioni di quarto d'ora (es. 7.5 = 7 ore e 30 minuti)."

    def clean_hours(self):
        hours = self.cleaned_data.get("hours")
        if hours is not None and hours < MIN_HOURS:
            raise forms.ValidationError("Le ore devono essere almeno 0,25 (un quarto d'ora).")
        if hours is not None and hours > 24:
            raise forms.ValidationError("Non puoi registrare più di 24 ore in un giorno.")
        return hours


class LeaveRequestForm(BaseBootstrapModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "kind", "start_date", "end_date", "hours", "reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = active_employees()
        self.fields["employee"].label_from_instance = lambda obj: f"{obj.full_name} ({obj.code})"
        self.fields["end_date"].help_text = "Per un solo giorno, indica la stessa data di inizio."

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        hours = cleaned.get("hours")
        if start and end and end < start:
            self.add_error("end_date", "La data di fine non può precedere quella di inizio.")
        if hours and start and end and start != end:
            self.add_error("hours", "Un permesso orario deve riferirsi a un solo giorno: lascia vuoto «Al» o indica la stessa data.")
        return cleaned


class BulkTimeEntryForm(forms.Form):
    """Inserimento rapido: le ore di tutti i dipendenti per una giornata."""

    date = forms.DateField(label="Giornata", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    kind = forms.ChoiceField(label="Tipo", choices=TimeEntry.KIND_CHOICES, initial=TimeEntry.KIND_ORDINARY)
    job = forms.ModelChoiceField(label="Cantiere", queryset=Job.objects.none(), required=False)
    description = forms.CharField(label="Descrizione attività", max_length=200, required=False)

    def __init__(self, *args, employees=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employees = list(employees or [])
        self.fields["job"].queryset = open_jobs()
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"
        for employee in self.employees:
            self.fields[self.hours_field(employee)] = forms.DecimalField(
                label=employee.full_name,
                required=False,
                min_value=MIN_HOURS,
                max_value=Decimal("24"),
                widget=forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.25", "min": "0", "placeholder": "—"}),
            )

    @staticmethod
    def hours_field(employee):
        return f"hours_{employee.pk}"

    def entries(self):
        """Righe valorizzate: lista di (dipendente, ore)."""
        result = []
        for employee in self.employees:
            hours = self.cleaned_data.get(self.hours_field(employee))
            if hours:
                result.append((employee, hours))
        return result

    def clean(self):
        cleaned = super().clean()
        if not self.entries() and not self.errors:
            raise forms.ValidationError("Indica almeno le ore di un dipendente.")
        return cleaned


class TimesheetFilterForm(forms.Form):
    """Filtro del registro presenze mensile."""

    year = forms.ChoiceField(label="Anno")
    month = forms.ChoiceField(label="Mese")

    def __init__(self, *args, year_choices=None, month_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"].choices = year_choices or []
        self.fields["month"].choices = month_choices or []
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select form-select-sm"


class StandardHoursForm(forms.Form):
    """Ore standard: riempie un periodo con le stesse ore ogni giorno lavorativo.

    Serve a chi lavora sempre lo stesso orario: invece di registrare 20 giornate
    una per una, si sceglie il periodo e le ore giornaliere.
    """

    employee = forms.ModelChoiceField(label="Dipendente", queryset=Employee.objects.none())
    start_date = forms.DateField(label="Dal", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(label="Al", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    hours = forms.DecimalField(
        label="Ore al giorno",
        initial=Decimal("8"),
        min_value=MIN_HOURS,
        max_value=Decimal("24"),
        widget=forms.NumberInput(attrs={"step": "0.25"}),
        help_text="Di norma 8 ore. Vengono create solo le giornate dal lunedì al venerdì.",
    )
    kind = forms.ChoiceField(label="Tipo", choices=TimeEntry.KIND_CHOICES, initial=TimeEntry.KIND_ORDINARY)
    job = forms.ModelChoiceField(label="Cantiere", queryset=Job.objects.none(), required=False)
    description = forms.CharField(label="Descrizione attività", max_length=200, required=False)
    include_saturday = forms.BooleanField(label="Includi il sabato", required=False)
    overwrite = forms.BooleanField(
        label="Sovrascrivi le giornate già registrate",
        required=False,
        help_text="Se lasci vuoto, i giorni che hanno già una registrazione vengono saltati.",
    )

    def __init__(self, *args, employees=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = employees if employees is not None else active_employees()
        self.fields["employee"].label_from_instance = lambda obj: f"{obj.full_name} ({obj.code})"
        self.fields["job"].queryset = open_jobs()
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["employee"].widget.attrs["class"] = "form-select"
        self.fields["kind"].widget.attrs["class"] = "form-select"
        self.fields["job"].widget.attrs["class"] = "form-select"
        for nome in ("start_date", "end_date"):
            self.fields[nome].widget.attrs["class"] = "form-control"
        for nome in ("hours", "description"):
            self.fields[nome].widget.attrs["class"] = "form-control"
        self.fields["include_saturday"].widget.attrs["class"] = "form-check-input"
        self.fields["overwrite"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned = super().clean()
        inizio = cleaned.get("start_date")
        fine = cleaned.get("end_date")
        if inizio and fine and fine < inizio:
            self.add_error("end_date", "La data di fine non può precedere quella di inizio.")
        elif inizio and fine and (fine - inizio).days > 366:
            self.add_error("end_date", "Il periodo non può superare un anno.")
        return cleaned

    def giorni(self):
        """Le date lavorative del periodo scelto (esclusa la domenica)."""
        inizio = self.cleaned_data["start_date"]
        fine = self.cleaned_data["end_date"]
        sabato = self.cleaned_data.get("include_saturday")
        giorni = []
        giorno = inizio
        while giorno <= fine:
            if giorno.weekday() < 5 or (sabato and giorno.weekday() == 5):
                giorni.append(giorno)
            giorno += timedelta(days=1)
        return giorni


class CollaboratorPhotoForm(forms.Form):
    """Foto caricata da un collaboratore: cantiere o bolla di acquisto."""

    kind = forms.ChoiceField(
        label="Cosa stai caricando",
        choices=[
            ("site", "Foto del cantiere (inizio o fine giornata)"),
            ("receipt", "Bolla o documento di acquisto"),
        ],
        initial="site",
        widget=forms.RadioSelect,
    )
    file = forms.FileField(
        label="Foto",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*,application/pdf", "capture": "environment"}),
    )
    job = forms.ModelChoiceField(label="Cantiere", queryset=Job.objects.none(), required=False)
    notes = forms.CharField(label="Nota (facoltativa)", max_length=200, required=False)

    def __init__(self, *args, collaborator=None, **kwargs):
        self.collaborator = collaborator
        super().__init__(*args, **kwargs)
        self.fields["job"].queryset = open_jobs()
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].help_text = "Facoltativo per le bolle, utile per le foto del cantiere."
        self.fields["kind"].widget.attrs["class"] = "form-check-input"
        self.fields["file"].widget.attrs["class"] = "form-control"
        self.fields["file"].help_text = "Le foto vengono ridimensionate automaticamente. Sono ammesse anche le bolle in PDF."
        self.fields["job"].widget.attrs["class"] = "form-select"
        self.fields["notes"].widget.attrs["class"] = "form-control"

    def clean_file(self):
        caricato = self.cleaned_data.get("file")
        if caricato and caricato.size > 25 * 1024 * 1024:
            raise forms.ValidationError("Il file supera i 25 MB: ridimensiona la foto e riprova.")
        return caricato


# ------------------------------------------------------------ collaboratori
class CollaboratorForm(BaseBootstrapModelForm):
    """Anagrafica di un collaboratore esterno."""

    class Meta:
        model = Collaborator
        fields = [
            "name",
            "company",
            "specialization",
            "contact",
            "user",
            "fiscal_code",
            "phone",
            "email",
            "hourly_rate",
            "active",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        from apps.contacts.models import Contact

        self.fields["contact"].queryset = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        self.fields["contact"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["contact"].required = False
        self.fields["user"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["user"].label_from_instance = lambda obj: obj.get_full_name() or obj.username
        self.fields["user"].required = False
        self.fields["user"].help_text = (
            "Facoltativo: crea un utente con il solo ruolo «Collaboratore» e collegalo qui, "
            "così può registrare le ore da solo."
        )

    def clean(self):
        cleaned = super().clean()
        utente = cleaned.get("user")
        if utente and self.instance.pk:
            altro = Collaborator.objects.filter(user=utente).exclude(pk=self.instance.pk).exists()
            if altro:
                self.add_error("user", "Questo utente è già collegato a un altro collaboratore.")
        return cleaned


class CollaboratorTimeEntryForm(BaseBootstrapModelForm):
    """Ore rendicontate da un collaboratore.

    Se ``collaborator`` è passato al form (area del collaboratore), il campo
    sparisce e le ore finiscono sempre su quello: un collaboratore non può
    registrare ore a nome di un altro.
    """

    class Meta:
        model = CollaboratorTimeEntry
        fields = ["collaborator", "date", "hours", "job", "description"]

    def __init__(self, *args, collaborator=None, **kwargs):
        self.fixed_collaborator = collaborator
        super().__init__(*args, **kwargs)
        if collaborator is not None:
            self.fields.pop("collaborator", None)
        else:
            self.fields["collaborator"].queryset = Collaborator.objects.filter(active=True).order_by("name")
            self.fields["collaborator"].label_from_instance = lambda obj: str(obj)
        self.fields["job"].queryset = open_jobs()
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["job"].required = False
        self.fields["job"].help_text = "Su quale cantiere o lavoro sono state fatte queste ore."
        self.fields["hours"].widget.attrs["step"] = "0.25"
        self.fields["hours"].widget.attrs["min"] = "0.25"
        self.fields["hours"].help_text = "In ore e quarti d'ora (es. 4.5 = 4 ore e 30 minuti)."

    def clean_hours(self):
        ore = self.cleaned_data.get("hours")
        if ore is not None and ore > 24:
            raise forms.ValidationError("Non puoi registrare più di 24 ore in un giorno.")
        return ore

    def save(self, commit=True):
        istanza = super().save(commit=False)
        if self.fixed_collaborator is not None:
            istanza.collaborator = self.fixed_collaborator
        if commit:
            istanza.save()
        return istanza
