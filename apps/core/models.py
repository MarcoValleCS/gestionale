"""Modelli di base: unità di misura, IVA, etichette, pagamenti, numerazioni."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from .utils import format_quantity, mescola_colori, normalizza_colore, rgba, schiarisci, scurisci
from .validators import valida_file_caricato

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

    CHIAVE_CACHE = "company_settings"

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
        """Dati azienda (record singolo), con cache breve.

        Vengono letti a ogni pagina dai context processor: senza cache sono due
        query per richiesta. La cache si azzera al salvataggio.
        """
        from .cache import memoizza

        def leggi():
            oggetto, _ = cls.objects.get_or_create(pk=1)
            return oggetto

        return memoizza(cls.CHIAVE_CACHE, leggi, 300)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from .cache import dimentica

        dimentica(self.CHIAVE_CACHE)

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
    file = models.FileField("File", upload_to="attachments/%Y/%m/", validators=[valida_file_caricato])
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


class InternalMessage(TimeStampedModel):
    """Messaggio interno fra utenti del gestionale (bacheca privata)."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_internal_messages",
        verbose_name="Mittente",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_internal_messages",
        verbose_name="Destinatario",
    )
    body = models.TextField("Messaggio")
    read_at = models.DateTimeField("Letto il", null=True, blank=True)

    class Meta:
        verbose_name = "Messaggio interno"
        verbose_name_plural = "Messaggi interni"
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="message_recipient_read_idx"),
            models.Index(fields=["sender", "recipient"], name="message_pair_idx"),
        ]

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.body[:40]}"

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])
        return self.read_at


class InboundEmail(TimeStampedModel):
    """Email scaricata dalla casella aziendale, per leggerla dal gestionale.

    Il messaggio viene copiato qui al momento della sincronizzazione: così la
    posta si legge senza aspettare il server IMAP, e resta consultabile anche
    quando la casella è momentaneamente irraggiungibile. Il corpo completo e gli
    allegati si scaricano alla prima apertura.
    """

    uid = models.CharField("UID IMAP", max_length=64, unique=True)
    folder = models.CharField("Cartella", max_length=60, default="INBOX")
    message_id = models.CharField("Message-ID", max_length=255, blank=True)
    sender_name = models.CharField("Mittente", max_length=200, blank=True)
    sender_email = models.EmailField("Email mittente", blank=True)
    recipients = models.CharField("Destinatari", max_length=500, blank=True)
    subject = models.CharField("Oggetto", max_length=300, blank=True)
    received_at = models.DateTimeField("Ricevuta il", null=True, blank=True)
    body_text = models.TextField("Testo", blank=True)
    body_html = models.TextField("HTML", blank=True)
    body_loaded = models.BooleanField("Corpo scaricato", default=False)
    attachments = models.JSONField("Allegati", default=list, blank=True)
    read_at = models.DateTimeField("Letta il", null=True, blank=True)
    is_reply = models.BooleanField("È una risposta", default=False)
    is_internal = models.BooleanField("Da dominio aziendale", default=False)
    is_relevant = models.BooleanField("Rilevante", default=False, db_index=True)
    relevance = models.CharField("Perché è rilevante", max_length=30, blank=True)
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails",
        verbose_name="Contatto collegato",
    )

    class Meta:
        verbose_name = "Email ricevuta"
        verbose_name_plural = "Posta ricevuta"
        ordering = ["-received_at", "-pk"]
        indexes = [
            models.Index(fields=["-received_at"], name="email_received_idx"),
            models.Index(fields=["read_at"], name="email_read_idx"),
        ]

    def __str__(self):
        return f"{self.sender_email}: {self.subject}"

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def has_attachments(self):
        return bool(self.attachments)

    @property
    def sender_label(self):
        return self.sender_name or self.sender_email or "(sconosciuto)"

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])
        return self.read_at


# ------------------------------------------------------------------- guida
class WikiPage(TimeStampedModel):
    """Pagina della guida: come si usa una funzione del gestionale.

    Ogni pagina è visibile solo ai ruoli indicati (vuoto = tutti), così ognuno
    trova le istruzioni delle funzioni che può davvero usare.
    """

    slug = models.SlugField("Indirizzo", max_length=90, unique=True, blank=True)
    title = models.CharField("Titolo", max_length=160)
    area = models.CharField("Sezione", max_length=60, default="Generale")
    summary = models.CharField("Sommario", max_length=250, blank=True)
    body = models.TextField("Contenuto", help_text="Testo della guida (titoli, elenchi, link).")
    roles = models.CharField(
        "Ruoli che possono leggerla",
        max_length=250,
        blank=True,
        help_text="Vuoto = tutti. Altrimenti i nomi dei ruoli separati da virgola (es. Vendite, Amministratore).",
    )
    order = models.PositiveSmallIntegerField("Ordine", default=100)
    is_published = models.BooleanField("Pubblicata", default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiki_pages",
        verbose_name="Modificata da",
    )

    class Meta:
        verbose_name = "Pagina della guida"
        verbose_name_plural = "Guida"
        ordering = ["area", "order", "title"]
        indexes = [models.Index(fields=["is_published", "area", "order"], name="wiki_visibile_idx")]

    def __str__(self):
        return self.title

    @property
    def elenco_ruoli(self):
        return [ruolo.strip() for ruolo in self.roles.split(",") if ruolo.strip()]

    def visible_to(self, utente):
        """True se questo utente può leggere la pagina."""
        if not utente or not getattr(utente, "is_authenticated", False):
            return False
        if not self.is_published:
            return False
        if utente.is_superuser:
            return True
        richiesti = self.elenco_ruoli
        if not richiesti:
            return True
        return utente.groups.filter(name__in=richiesti).exists()

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        from .richtext import clean_guida

        self.body = clean_guida(self.body)
        if not self.slug:
            base = slugify(self.title)[:80] or "pagina"
            slug = base
            numero = 2
            while WikiPage.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{numero}"
                numero += 1
            self.slug = slug
        return super().save(*args, **kwargs)


# ------------------------------------------------- menu condivisi in cache
# I menu di unità di misura e aliquote IVA sono uguali in tutte le righe di un
# documento: si tengono in cache (vedi ``menu_unita`` e ``menu_aliquote``) e si
# rinnovano appena qualcuno li modifica.
from django.db.models.signals import post_delete, post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402

from .cache import dimentica  # noqa: E402


@receiver([post_save, post_delete], sender=UnitOfMeasure)
def _unita_di_misura_cambiata(sender, **kwargs):
    dimentica("menu_unita")


@receiver([post_save, post_delete], sender=VatRate)
def _aliquota_cambiata(sender, **kwargs):
    dimentica("menu_aliquote")
