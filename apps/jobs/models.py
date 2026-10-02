"""Cantieri/commesse, manutenzioni programmate e seriali installati."""
import calendar
from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.contacts.models import Contact
from apps.core.models import TimeStampedModel


def add_months(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def add_months_keep_day(value, months):
    year, month = add_months(value.year, value.month, months)
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Job(TimeStampedModel):
    """Cantiere / commessa: il «contenitore» di un lavoro (es. una piscina)."""

    STATUS_SURVEY = "survey"
    STATUS_QUOTE = "quote"
    STATUS_CONFIRMED = "confirmed"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_TESTING = "testing"
    STATUS_CLOSED = "closed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_SURVEY, "Sopralluogo"),
        (STATUS_QUOTE, "In preventivazione"),
        (STATUS_CONFIRMED, "Confermato"),
        (STATUS_IN_PROGRESS, "In esecuzione"),
        (STATUS_TESTING, "Collaudo"),
        (STATUS_CLOSED, "Chiuso"),
        (STATUS_CANCELLED, "Annullato"),
    ]
    OPEN_STATUSES = [STATUS_SURVEY, STATUS_QUOTE, STATUS_CONFIRMED, STATUS_IN_PROGRESS, STATUS_TESTING]

    code = models.CharField("Codice", max_length=20, unique=True, blank=True)
    name = models.CharField("Nome cantiere", max_length=150)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="jobs", verbose_name="Cliente")
    status = models.CharField("Stato", max_length=20, choices=STATUS_CHOICES, default=STATUS_SURVEY)
    address = models.CharField("Indirizzo", max_length=200, blank=True)
    zip_code = models.CharField("CAP", max_length=10, blank=True)
    city = models.CharField("Città", max_length=100, blank=True)
    province = models.CharField("Provincia", max_length=5, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_jobs",
        verbose_name="Responsabile",
    )
    start_date = models.DateField("Inizio lavori", null=True, blank=True)
    end_date = models.DateField("Fine prevista", null=True, blank=True)
    notes = models.TextField("Note", blank=True)

    class Meta:
        verbose_name = "Cantiere"
        verbose_name_plural = "Cantieri"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="job_status_created_idx"),
            models.Index(fields=["customer", "name"], name="job_customer_name_idx"),
        ]

    def __str__(self):
        return f"{self.code} – {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            super().save(*args, **kwargs)
            self.code = f"CAN{self.pk:05d}"
            return super().save(update_fields=["code"])
        return super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def full_address(self):
        parts = [self.address]
        if self.zip_code or self.city:
            parts.append(f"{self.zip_code} {self.city}".strip())
        return ", ".join(part for part in parts if part)


class MaintenancePlan(TimeStampedModel):
    """Manutenzione programmata (canone, apertura/chiusura piscina, ecc.)."""

    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_BIMONTHLY = "bimonthly"
    FREQUENCY_QUARTERLY = "quarterly"
    FREQUENCY_SEMIANNUAL = "semiannual"
    FREQUENCY_ANNUAL = "annual"
    FREQUENCY_CUSTOM = "custom"
    FREQUENCY_CHOICES = [
        (FREQUENCY_MONTHLY, "Mensile"),
        (FREQUENCY_BIMONTHLY, "Bimestrale"),
        (FREQUENCY_QUARTERLY, "Trimestrale"),
        (FREQUENCY_SEMIANNUAL, "Semestrale"),
        (FREQUENCY_ANNUAL, "Annuale"),
        (FREQUENCY_CUSTOM, "Personalizzata"),
    ]
    FREQUENCY_MONTHS = {
        FREQUENCY_MONTHLY: 1,
        FREQUENCY_BIMONTHLY: 2,
        FREQUENCY_QUARTERLY: 3,
        FREQUENCY_SEMIANNUAL: 6,
        FREQUENCY_ANNUAL: 12,
        FREQUENCY_CUSTOM: 12,
    }

    name = models.CharField("Descrizione", max_length=150)
    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="maintenance_plans", verbose_name="Cliente")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_plans", verbose_name="Cantiere")
    template = models.ForeignKey(
        "sales.QuoteTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_plans",
        verbose_name="Modello di preventivo",
    )
    frequency = models.CharField("Frequenza", max_length=20, choices=FREQUENCY_CHOICES, default=FREQUENCY_ANNUAL)
    next_date = models.DateField("Prossima esecuzione", default=timezone.localdate)
    notes = models.TextField("Note", blank=True)
    active = models.BooleanField("Attiva", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_plans", verbose_name="Creato da"
    )

    class Meta:
        verbose_name = "Manutenzione programmata"
        verbose_name_plural = "Manutenzioni programmate"
        ordering = ["next_date", "name"]
        indexes = [models.Index(fields=["active", "next_date"], name="plan_active_next_idx")]

    def __str__(self):
        return f"{self.name} – {self.customer.name}"

    def is_due(self, days=30):
        return self.active and self.next_date <= timezone.localdate() + timedelta(days=days)

    def is_overdue(self):
        return self.active and self.next_date < timezone.localdate()

    def advance(self):
        months = self.FREQUENCY_MONTHS.get(self.frequency, 12)
        self.next_date = add_months_keep_day(self.next_date, months)
        self.save(update_fields=["next_date", "updated_at"])
        return self.next_date

