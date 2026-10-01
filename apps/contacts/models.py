from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import PaymentTerm, Tag, TimeStampedModel


class Contact(TimeStampedModel):
    """Cliente, fornitore o entrambi."""

    code = models.CharField("Codice", max_length=20, unique=True, blank=True)
    name = models.CharField("Ragione sociale / Nome", max_length=200)
    is_customer = models.BooleanField("Cliente", default=True)
    is_supplier = models.BooleanField("Fornitore", default=False)

    vat_number = models.CharField("Partita IVA", max_length=20, blank=True)
    tax_code = models.CharField("Codice fiscale", max_length=20, blank=True)
    sdi_code = models.CharField("Codice destinatario SDI", max_length=10, blank=True)
    pec = models.EmailField("PEC", blank=True)

    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefono", max_length=40, blank=True)
    mobile = models.CharField("Cellulare", max_length=40, blank=True)
    website = models.CharField("Sito web", max_length=200, blank=True)

    address = models.CharField("Indirizzo", max_length=200, blank=True)
    zip_code = models.CharField("CAP", max_length=10, blank=True)
    city = models.CharField("Città", max_length=100, blank=True)
    province = models.CharField("Provincia", max_length=5, blank=True)
    country = models.CharField("Paese", max_length=100, blank=True, default="Italia")

    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Condizione di pagamento",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts", verbose_name="Etichette")
    notes = models.TextField("Note", blank=True)
    active = models.BooleanField("Attivo", default=True)

    class Meta:
        verbose_name = "Contatto"
        verbose_name_plural = "Contatti"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["active", "name"], name="contact_active_name_idx"),
            models.Index(fields=["vat_number"], name="contact_vat_idx"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if not self.is_customer and not self.is_supplier:
            raise ValidationError("Il contatto deve essere almeno cliente o fornitore.")

    def save(self, *args, **kwargs):
        if not self.code:
            if self.is_customer and not self.is_supplier:
                prefix = "CLI"
            elif self.is_supplier and not self.is_customer:
                prefix = "FOR"
            else:
                prefix = "CNT"
            super().save(*args, **kwargs)
            self.code = f"{prefix}{self.pk:05d}"
            return super().save(update_fields=["code"])
        return super().save(*args, **kwargs)

    @property
    def kind_label(self):
        if self.is_customer and self.is_supplier:
            return "Cliente e fornitore"
        if self.is_customer:
            return "Cliente"
        return "Fornitore"
