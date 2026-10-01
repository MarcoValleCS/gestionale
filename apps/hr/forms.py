"""Form di dipendenti, registrazione ore e ferie/permessi."""
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import BaseBootstrapModelForm
from apps.jobs.models import Job

from .models import Employee, LeaveRequest, TimeEntry

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
