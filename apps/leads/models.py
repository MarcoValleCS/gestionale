"""Pipeline dei lead: potenziali clienti dalle prime richieste al contratto."""
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.contacts.models import Contact
from apps.core.models import Tag, TimeStampedModel


class LeadStage(models.Model):
    """Fase della trattativa (personalizzabile: Impostazioni → Fasi lead)."""

    KIND_OPEN = "open"
    KIND_WON = "won"
    KIND_LOST = "lost"
    KIND_CHOICES = [
        (KIND_OPEN, "In corso"),
        (KIND_WON, "Vinta"),
        (KIND_LOST, "Persa"),
    ]

    name = models.CharField("Nome", max_length=60, unique=True)
    order = models.PositiveIntegerField("Ordine", default=0)
    color = models.CharField("Colore", max_length=20, choices=Tag.COLOR_CHOICES, default="secondary")
    kind = models.CharField("Esito", max_length=10, choices=KIND_CHOICES, default=KIND_OPEN)
    on_quote_created = models.BooleanField(
        "Fase «Preventivo mandato»",
        default=False,
        help_text="Quando si crea un preventivo dal lead, la trattativa passa in questa fase.",
    )

    class Meta:
        verbose_name = "Fase lead"
        verbose_name_plural = "Fasi lead"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Lead(TimeStampedModel):
    """Potenziale cliente: dal primo contatto alla chiusura del contratto."""

    name = models.CharField("Riferimento", max_length=150, help_text="Es. «Rossi – piscina via Verdi».")
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", verbose_name="Contatto"
    )
    phone = models.CharField("Telefono", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    city = models.CharField("Città", max_length=100, blank=True)
    source = models.CharField(
        "Provenienza", max_length=80, blank=True, help_text="Es. passaparola, sito, Google, social."
    )
    stage = models.ForeignKey(LeadStage, on_delete=models.PROTECT, related_name="leads", verbose_name="Fase")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name="Responsabile",
    )
    estimated_value = models.DecimalField("Valore stimato", max_digits=12, decimal_places=2, default=Decimal("0"))
    next_action = models.DateField("Prossima azione", null=True, blank=True)
    quote = models.ForeignKey(
        "sales.Quote", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", verbose_name="Preventivo"
    )
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", verbose_name="Cantiere"
    )
    notes = models.TextField("Note", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_created",
        verbose_name="Creato da",
    )

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Lead"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["stage", "-created_at"], name="lead_stage_date_idx"),
            models.Index(fields=["next_action"], name="lead_next_action_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_open(self):
        return self.stage.kind == LeadStage.KIND_OPEN

    @property
    def is_won(self):
        return self.stage.kind == LeadStage.KIND_WON

    @property
    def is_lost(self):
        return self.stage.kind == LeadStage.KIND_LOST

    def next_stage(self):
        """Fase successiva «in corso», altrimenti la fase vinta."""
        if not self.is_open:
            return None
        successiva = LeadStage.objects.filter(kind=LeadStage.KIND_OPEN, order__gt=self.stage.order).order_by("order").first()
        if successiva:
            return successiva
        return LeadStage.objects.filter(kind=LeadStage.KIND_WON).order_by("order").first()
