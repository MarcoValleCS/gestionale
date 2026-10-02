"""Modelli di base: unità di misura, IVA, etichette, pagamenti, numerazioni."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from .utils import format_quantity, mescola_colori, normalizza_colore, rgba, schiarisci, scurisci

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Creato il", auto_now_add=True)
    updated_at = models.DateTimeField("Aggiornato il", auto_now=True)

    class Meta:
        abstract = True


class UnitOfMeasure(models.Model):
    code = models.CharField("Codice", max_length=10, unique=True, help_text="Es. PZ, KG, MT")
    name = models.CharField("Descrizione", max_length=60)
    is_active = models.BooleanField("Attiva", default=True)

    class Meta:
        verbose_name = "Unità di misura"
        verbose_name_plural = "Unità di misura"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class VatRate(models.Model):
    code = models.CharField("Codice", max_length=10, unique=True, help_text="Es. 22, 10, N2.2")
    name = models.CharField("Descrizione", max_length=120)
    rate = models.DecimalField("Aliquota %", max_digits=5, decimal_places=2, default=Decimal("22.00"))
    nature = models.CharField(
        "Natura (fatturazione elettronica)",
        max_length=10,
        blank=True,
        help_text="Codice natura SDI, es. N2.2. Lasciare vuoto per le aliquote ordinarie.",
    )
    is_default_sales = models.BooleanField("Predefinita per vendite", default=False)
    is_default_purchase = models.BooleanField("Predefinita per acquisti", default=False)
    is_active = models.BooleanField("Attiva", default=True)

    class Meta:
        verbose_name = "Aliquota IVA"
        verbose_name_plural = "Aliquote IVA"
        ordering = ["-rate", "code"]

    def __str__(self):
        if self.rate:
            return f"{format_quantity(self.rate)}% – {self.name}"
        return f"{self.name}"

    def clean(self):
        if self.is_default_sales and not self.is_active:
            raise ValidationError({"is_default_sales": "Un'aliquota disattivata non può essere predefinita."})

    @classmethod
    def default_for_sales(cls):
        return cls.objects.filter(is_active=True, is_default_sales=True).first() or cls.objects.filter(is_active=True).order_by("-rate").first()

    @classmethod
    def default_for_purchase(cls):
        return cls.objects.filter(is_active=True, is_default_purchase=True).first() or cls.objects.filter(is_active=True).order_by("-rate").first()


class Tag(models.Model):
    COLOR_CHOICES = [
        ("primary", "Blu"),
        ("success", "Verde"),
        ("danger", "Rosso"),
        ("warning", "Giallo"),
        ("info", "Azzurro"),
        ("secondary", "Grigio"),
        ("dark", "Scuro"),
    ]

    name = models.CharField("Nome", max_length=60, unique=True)
    color = models.CharField("Colore", max_length=20, choices=COLOR_CHOICES, default="secondary")
    description = models.CharField("Descrizione", max_length=200, blank=True)

    class Meta:
        verbose_name = "Etichetta"
        verbose_name_plural = "Etichette"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaymentTerm(models.Model):
    name = models.CharField("Nome", max_length=80, unique=True)
    days = models.PositiveIntegerField("Giorni", default=30)
    end_of_month = models.BooleanField("Fine mese", default=False)
    notes = models.CharField("Note", max_length=200, blank=True)

    class Meta:
        verbose_name = "Condizione di pagamento"
        verbose_name_plural = "Condizioni di pagamento"
        ordering = ["days", "name"]

    def __str__(self):
        return self.name


class NumberSequence(models.Model):
    DOC_TYPE_QUOTE = "quote"
    DOC_TYPE_SALES_ORDER = "sales_order"
    DOC_TYPE_PURCHASE_ORDER = "purchase_order"
    DOC_TYPE_DELIVERY_NOTE = "delivery_note"
    DOC_TYPE_SALES_INVOICE = "sales_invoice"
    DOC_TYPE_PURCHASE_INVOICE = "purchase_invoice"
    DOC_TYPE_CHOICES = [
        (DOC_TYPE_QUOTE, "Preventivo"),
        (DOC_TYPE_SALES_ORDER, "Ordine cliente"),
        (DOC_TYPE_PURCHASE_ORDER, "Ordine fornitore"),
        (DOC_TYPE_DELIVERY_NOTE, "DDT"),
        (DOC_TYPE_SALES_INVOICE, "Fattura emessa"),
        (DOC_TYPE_PURCHASE_INVOICE, "Fattura ricevuta"),
    ]
    DEFAULT_PREFIXES = {
        DOC_TYPE_QUOTE: "PRE-",
        DOC_TYPE_SALES_ORDER: "OC-",
        DOC_TYPE_PURCHASE_ORDER: "OF-",
        DOC_TYPE_DELIVERY_NOTE: "DDT-",
        DOC_TYPE_SALES_INVOICE: "FT-",
        DOC_TYPE_PURCHASE_INVOICE: "FA-",
    }

    doc_type = models.CharField("Tipo documento", max_length=30, choices=DOC_TYPE_CHOICES)
    year = models.PositiveSmallIntegerField("Anno", default=0, help_text="0 = numerazione continua senza anno")
    prefix = models.CharField("Prefisso", max_length=20)
    next_number = models.PositiveIntegerField("Prossimo numero", default=1)
    padding = models.PositiveSmallIntegerField("Zeri iniziali", default=4)

    class Meta:
        verbose_name = "Numerazione"
        verbose_name_plural = "Numerazioni"
        ordering = ["doc_type", "year"]
        constraints = [models.UniqueConstraint(fields=["doc_type", "year"], name="unique_sequence_per_type_year")]

    def __str__(self):
        return f"{self.get_doc_type_display()} {self.year or ''}".strip()

    @classmethod
    def get_for(cls, doc_type):
        year = timezone.localdate().year
        obj, created = cls.objects.get_or_create(
            doc_type=doc_type,
            year=year,
            defaults={"prefix": cls.DEFAULT_PREFIXES.get(doc_type, f"{doc_type.upper()}-")},
        )
        return obj

    def take_next_number(self):
        """Restituisce il prossimo numero del documento e incrementa il contatore.

        L'incremento è un ``UPDATE`` atomico a livello di database, non una
        lettura seguita da una scrittura: due utenti che creano un documento
        nello stesso istante non possono quindi ottenere lo stesso numero.

        Serve perché ``select_for_update`` non ha effetto su SQLite (non
        supporta il blocco di riga). Con l'UPDATE il blocco di scrittura viene
        preso comunque e la seconda transazione si mette in coda, leggendo il
        valore già incrementato. Su PostgreSQL l'UPDATE blocca la riga e
        l'altra transazione attende il commit.

        Il vincolo ``unique`` sul numero dei documenti resta come ultima rete
        di sicurezza.
        """
        with transaction.atomic():
            type(self).objects.filter(pk=self.pk).update(next_number=F("next_number") + 1)
            after = type(self).objects.values_list("next_number", flat=True).get(pk=self.pk)
            number = after - 1

        self.next_number = after
        base = f"{self.prefix}{(self.year or '')}-" if self.year else self.prefix
        return f"{base}{number:0{self.padding}d}"


class CompanySettings(models.Model):
    """Dati dell'azienda (record singolo)."""

    name = models.CharField("Ragione sociale", max_length=200, default="La mia azienda")
    vat_number = models.CharField("Partita IVA", max_length=20, blank=True)
    tax_code = models.CharField("Codice fiscale", max_length=20, blank=True)
    pec = models.EmailField("PEC", blank=True, help_text="Usata anche per l'invio delle fatture elettroniche allo SDI.")
    fiscal_regime = models.CharField(
        "Regime fiscale",
        max_length=10,
        default="RF01",
        choices=[
            ("RF01", "RF01 – Ordinario"),
            ("RF02", "RF02 – Contribuenti minimi"),
            ("RF04", "RF04 – Agricoltura e pesca"),
            ("RF05", "RF05 – Vendita sali e tabacchi"),
            ("RF15", "RF15 – Agenzie viaggi"),
            ("RF16", "RF16 – Agenti e rappresentanti"),
            ("RF17", "RF17 – Vendita porta a porta"),
            ("RF18", "RF18 – Altri casi"),
            ("RF19", "RF19 – Regime forfettario"),
        ],
        help_text="Serve per la fatturazione elettronica (campo RegimeFiscale).",
    )
    address = models.CharField("Indirizzo", max_length=200, blank=True)
    zip_code = models.CharField("CAP", max_length=10, blank=True)
    city = models.CharField("Città", max_length=100, blank=True)
    province = models.CharField("Provincia", max_length=5, blank=True)
    country = models.CharField("Paese", max_length=100, default="Italia")
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefono", max_length=40, blank=True)
    website = models.CharField("Sito web", max_length=200, blank=True)
    iban = models.CharField("IBAN", max_length=40, blank=True)
    logo = models.ImageField("Logo aziendale", upload_to="company/", null=True, blank=True, help_text="Usato in alto nei documenti stampati (PNG o JPG).")
    document_color = models.CharField(
        "Colore documenti",
        max_length=7,
        default="#1d4ed8",
        help_text="Colore principale di grafica e intestazioni nei documenti stampati.",
    )
    quote_footer = models.TextField(
        "Condizioni generali (in fondo ai documenti)",
        blank=True,
        default="Pagamento: come concordato.\nPrezzi IVA esclusa salvo diversa indicazione.",
    )

    # -------------------------------------------------------- aspetto grafico
    BACKGROUND_CHOICES = [
        ("soft", "Azzurro tenue"),
        ("white", "Bianco"),
        ("grey", "Grigio chiaro"),
        ("warm", "Caldo"),
        ("blue", "Azzurro"),
    ]
    BACKGROUND_COLORS = {
        "soft": "#f4f6fb",
        "white": "#ffffff",
        "grey": "#eef0f3",
        "warm": "#faf7f1",
        "blue": "#eaf2fc",
    }
    DOCUMENT_STYLE_CHOICES = [
        ("classico", "Classico"),
        ("moderno", "Moderno"),
        ("sobrio", "Sobrio"),
        ("elegante", "Elegante"),
    ]

    app_logo = models.ImageField(
        "Logo del gestionale",
        upload_to="company/",
        null=True,
        blank=True,
        help_text="Sostituisce l'icona in alto a sinistra nel gestionale (PNG con sfondo trasparente).",
    )
    theme_color = models.CharField(
        "Colore del gestionale",
        max_length=7,
        default="#2563eb",
        help_text="Colore di menu, pulsanti e collegamenti.",
    )
    theme_background = models.CharField(
        "Sfondo del gestionale",
        max_length=10,
        choices=BACKGROUND_CHOICES,
        default="soft",
    )
    document_style = models.CharField(
        "Stile dei preventivi e documenti",
        max_length=10,
        choices=DOCUMENT_STYLE_CHOICES,
        default="classico",
    )

    class Meta:
        verbose_name = "Dati azienda"
        verbose_name_plural = "Dati azienda"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # ------------------------------------------------------------- colori
    @property
    def theme_color_hex(self):
        return normalizza_colore(self.theme_color)

    @property
    def theme_color_dark(self):
        return scurisci(self.theme_color_hex, 0.22)

    @property
    def theme_color_soft(self):
        return schiarisci(self.theme_color_hex, 0.88)

    @property
    def background_hex(self):
        return self.BACKGROUND_COLORS.get(self.theme_background, "#f4f6fb")

    @property
    def sidebar_colors(self):
        """Toni della barra laterale derivati dal colore principale."""
        colore = self.theme_color_hex
        return {
            "top": mescola_colori(colore, "#0b1224", 0.86),
            "mid": mescola_colori(colore, "#0b1224", 0.78),
            "bottom": mescola_colori(colore, "#0b1224", 0.74),
            "glow": rgba(colore, 0.35),
            "active": rgba(colore, 0.95),
        }

    @property
    def logo_url(self):
        try:
            return self.logo.url if self.logo else ""
        except ValueError:
            return ""

    @property
    def app_logo_url(self):
        """Logo del gestionale caricato dall'utente (vuoto se non impostato)."""
        try:
            return self.app_logo.url if self.app_logo else ""
        except ValueError:
            return ""


class Attachment(TimeStampedModel):
    """Allegato su articolo, cantiere o collaboratore (schede tecniche, foto, bolle)."""

    KIND_DOCUMENT = "document"
    KIND_SITE = "site"
    KIND_RECEIPT = "receipt"
    KIND_CHOICES = [
        (KIND_DOCUMENT, "Documento"),
        (KIND_SITE, "Foto cantiere"),
        (KIND_RECEIPT, "Bolla / acquisto"),
    ]

    name = models.CharField("Nome", max_length=150, blank=True)
    file = models.FileField("File", upload_to="attachments/%Y/%m/")
    notes = models.CharField("Note", max_length=200, blank=True)
    kind = models.CharField("Tipo", max_length=20, choices=KIND_CHOICES, default=KIND_DOCUMENT)
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, null=True, blank=True, related_name="attachments", verbose_name="Articolo"
    )
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.CASCADE, null=True, blank=True, related_name="attachments", verbose_name="Cantiere"
    )
    collaborator = models.ForeignKey(
        "hr.Collaborator",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="photos",
        verbose_name="Collaboratore",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments", verbose_name="Caricato da"
    )

    class Meta:
        verbose_name = "Allegato"
        verbose_name_plural = "Allegati"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind", "-created_at"], name="attachment_kind_date_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(product__isnull=False) | models.Q(job__isnull=False) | models.Q(collaborator__isnull=False),
                name="attachment_has_target",
            )
        ]

    def __str__(self):
        return self.name or self.file.name

    def save(self, *args, **kwargs):
        if not self.name and self.file:
            self.name = self.file.name.rsplit("/", 1)[-1]
        # le immagini nuove vengono raddrizzate e compresse; i file già salvati no
        if self.file and not getattr(self.file, "_committed", True):
            from .images import comprimi_immagine

            comprimi_immagine(self.file)
        return super().save(*args, **kwargs)

    @property
    def is_image(self):
        return self.file.name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

    @property
    def size_kb(self):
        try:
            return round(self.file.size / 1024, 1)
        except Exception:
            return None


class ActivityLog(models.Model):
    """Riga del registro modifiche: chi ha fatto cosa e quando."""

    ACTION_CHOICES = [
        ("creato", "Creato"),
        ("modificato", "Modificato"),
        ("cancellato", "Cancellato"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        verbose_name="Utente",
    )
    action = models.CharField("Azione", max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField("Tipo", max_length=60)
    object_id = models.CharField("Identificativo", max_length=40, blank=True)
    object_label = models.CharField("Oggetto", max_length=120, blank=True)
    details = models.CharField("Dettagli", max_length=300, blank=True)
    created_at = models.DateTimeField("Quando", auto_now_add=True)

    class Meta:
        verbose_name = "Attività"
        verbose_name_plural = "Registro attività"
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["-created_at"], name="activity_date_idx")]

    def __str__(self):
        return f"{self.get_action_display()} {self.model_name} {self.object_label}".strip()
