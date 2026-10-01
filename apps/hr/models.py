"""Dipendenti, registrazione delle ore lavorate e ferie/permessi."""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

ZERO = Decimal("0")


def working_days(start, end):
    """Giorni lavorativi (lun–ven) fra due date, estremi inclusi."""
    if not start or not end or end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)
    return total


def clamp_to_year(start, end, year):
    """Ritaglia un intervallo sull'anno indicato."""
    first = date(year, 1, 1)
    last = date(year, 12, 31)
    return max(start, first), min(end, last)


class Employee(TimeStampedModel):
    """Dipendente dell'azienda."""

    code = models.CharField("Codice", max_length=20, unique=True, blank=True)
    first_name = models.CharField("Nome", max_length=80)
    last_name = models.CharField("Cognome", max_length=80)
    fiscal_code = models.CharField("Codice fiscale", max_length=16, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefono", max_length=40, blank=True)
    qualification = models.CharField("Mansione", max_length=100, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee",
        verbose_name="Utente collegato",
    )
    hired_on = models.DateField("Data assunzione", null=True, blank=True)
    terminated_on = models.DateField("Data cessazione", null=True, blank=True)
    contract_weekly_hours = models.DecimalField("Ore settimanali da contratto", max_digits=5, decimal_places=2, default=Decimal("40"))
    hourly_cost = models.DecimalField("Costo orario (€)", max_digits=8, decimal_places=2, null=True, blank=True)
    holiday_days_per_year = models.DecimalField("Ferie annue (giorni)", max_digits=5, decimal_places=2, default=Decimal("26"))
    rol_hours_per_year = models.DecimalField("Permessi annui (ore)", max_digits=6, decimal_places=2, default=ZERO)
    active = models.BooleanField("Attivo", default=True)
    notes = models.TextField("Note", blank=True)

    class Meta:
        verbose_name = "Dipendente"
        verbose_name_plural = "Dipendenti"
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["active", "last_name"], name="employee_active_name_idx")]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.code:
            super().save(*args, **kwargs)
            self.code = f"DIP{self.pk:05d}"
            return super().save(update_fields=["code"])
        return super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}".strip()

    @property
    def is_current(self):
        """True se il rapporto è in corso (o non datato)."""
        if not self.active:
            return False
        return self.terminated_on is None or self.terminated_on >= timezone.localdate()

    # ------------------------------------------------------------------ ore
    def hours_between(self, start, end, kind=None):
        entries = self.time_entries.filter(date__gte=start, date__lte=end)
        if kind:
            entries = entries.filter(kind=kind)
        return entries.aggregate(total=models.Sum("hours"))["total"] or ZERO

    def hours_in_month(self, year, month, kind=None):
        entries = self.time_entries.filter(date__year=year, date__month=month)
        if kind:
            entries = entries.filter(kind=kind)
        return entries.aggregate(total=models.Sum("hours"))["total"] or ZERO

    # ---------------------------------------------------------------- ferie
    def leave_used(self, year, kind):
        """Giorni (o ore per i permessi orari) fruiti nell'anno per un tipo."""
        total = ZERO
        requests = self.leave_requests.filter(
            kind=kind,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__year__lte=year,
            end_date__year__gte=year,
        )
        for request in requests:
            if request.hours:
                total += request.hours
            else:
                start, end = clamp_to_year(request.start_date, request.end_date, year)
                total += working_days(start, end)
        return total

    def holiday_balance(self, year):
        """Ferie residue nell'anno (giorni)."""
        return self.holiday_days_per_year - self.leave_used(year, LeaveRequest.KIND_HOLIDAY)

    def rol_balance(self, year):
        """Permessi (ROL) residui nell'anno, in ore."""
        return self.rol_hours_per_year - self.leave_used(year, LeaveRequest.KIND_ROL)


class TimeEntry(TimeStampedModel):
    """Ore lavorate da un dipendente in una giornata."""

    KIND_ORDINARY = "ordinary"
    KIND_OVERTIME = "overtime"
    KIND_TRAVEL = "travel"
    KIND_CHOICES = [
        (KIND_ORDINARY, "Ordinario"),
        (KIND_OVERTIME, "Straordinario"),
        (KIND_TRAVEL, "Trasferta"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="time_entries", verbose_name="Dipendente")
    date = models.DateField("Data", default=timezone.localdate)
    hours = models.DecimalField(
        "Ore", max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.25"))]
    )
    kind = models.CharField("Tipo", max_length=20, choices=KIND_CHOICES, default=KIND_ORDINARY)
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="time_entries", verbose_name="Cantiere"
    )
    description = models.CharField("Descrizione attività", max_length=200, blank=True)
    billable = models.BooleanField("Addebitabile al cliente", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_time_entries",
        verbose_name="Registrato da",
    )

    class Meta:
        verbose_name = "Registrazione ore"
        verbose_name_plural = "Registrazioni ore"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["date", "employee"], name="timeentry_date_emp_idx"),
            models.Index(fields=["employee", "-date"], name="timeentry_emp_date_idx"),
        ]

    def __str__(self):
        return f"{self.employee} · {self.date:%d/%m/%Y} · {self.hours}h"

    @property
    def cost(self):
        if self.employee.hourly_cost is None:
            return None
        return self.employee.hourly_cost * self.hours


class LeaveRequest(TimeStampedModel):
    """Ferie, permessi, malattia o assenza di un dipendente."""

    KIND_HOLIDAY = "holiday"
    KIND_ROL = "rol"
    KIND_SICK = "sick"
    KIND_UNPAID = "unpaid"
    KIND_OTHER = "other"
    KIND_CHOICES = [
        (KIND_HOLIDAY, "Ferie"),
        (KIND_ROL, "Permessi (ROL)"),
        (KIND_SICK, "Malattia"),
        (KIND_UNPAID, "Non retribuito"),
        (KIND_OTHER, "Altro"),
    ]

    STATUS_REQUESTED = "requested"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Richiesta"),
        (STATUS_APPROVED, "Approvata"),
        (STATUS_REJECTED, "Rifiutata"),
        (STATUS_CANCELLED, "Annullata"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests", verbose_name="Dipendente")
    kind = models.CharField("Tipo", max_length=20, choices=KIND_CHOICES, default=KIND_HOLIDAY)
    start_date = models.DateField("Dal")
    end_date = models.DateField("Al")
    hours = models.DecimalField(
        "Ore (solo permessi orari)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Compila solo per un permesso di poche ore nello stesso giorno; altrimenti lascia vuoto.",
    )
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    reason = models.CharField("Motivo", max_length=200, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_leaves",
        verbose_name="Approvata da",
    )
    approved_at = models.DateTimeField("Approvata il", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leaves",
        verbose_name="Inserita da",
    )

    class Meta:
        verbose_name = "Ferie/permesso"
        verbose_name_plural = "Ferie e permessi"
        ordering = ["-start_date", "-pk"]
        indexes = [
            models.Index(fields=["status", "-start_date"], name="leave_status_start_idx"),
            models.Index(fields=["employee", "-start_date"], name="leave_emp_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="leave_end_after_start",
            )
        ]

    def __str__(self):
        return f"{self.employee} · {self.get_kind_display()} · {self.start_date:%d/%m/%Y}"

    @property
    def days(self):
        """Giorni lavorativi richiesti (0 se è un permesso orario)."""
        if self.hours:
            return 0
        return working_days(self.start_date, self.end_date)

    @property
    def duration_label(self):
        if self.hours:
            return f"{self.hours:g} h"
        giorni = self.days
        return f"{giorni} giorn{'o' if giorni == 1 else 'i'}"

    @property
    def is_pending(self):
        return self.status == self.STATUS_REQUESTED

    def approve(self, user):
        self.status = self.STATUS_APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return self

    def reject(self, user):
        self.status = self.STATUS_REJECTED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return self
