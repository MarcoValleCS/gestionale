from decimal import Decimal

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.contacts.models import Contact
from apps.core.models import Tag, TimeStampedModel, UnitOfMeasure, VatRate


class Category(models.Model):
    name = models.CharField("Nome", max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Categoria superiore",
    )
    notes = models.CharField("Note", max_length=200, blank=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorie"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def full_name(self):
        if self.parent:
            return f"{self.parent.name} › {self.name}"
        return self.name


class Product(TimeStampedModel):
    code = models.CharField("Codice", max_length=30, unique=True, blank=True)
    name = models.CharField("Descrizione", max_length=200)
    description = models.TextField("Descrizione estesa", blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="Categoria"
    )
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name="products", verbose_name="Unità di misura")
    barcode = models.CharField("Codice a barre", max_length=50, blank=True)

    sale_price = models.DecimalField("Prezzo vendita", max_digits=12, decimal_places=4, default=Decimal("0"))
    sale_vat = models.ForeignKey(
        VatRate, on_delete=models.PROTECT, related_name="sale_products", verbose_name="IVA vendita"
    )
    purchase_price = models.DecimalField(
        "Prezzo acquisto", max_digits=12, decimal_places=4, default=Decimal("0"),
        help_text="Usato come riferimento quando il fornitore non ha un listino.",
    )
    purchase_vat = models.ForeignKey(
        VatRate, on_delete=models.PROTECT, related_name="purchase_products", verbose_name="IVA acquisto"
    )
    main_supplier = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplied_products",
        verbose_name="Fornitore abituale",
    )

    is_stock_tracked = models.BooleanField("Gestito a magazzino", default=True)
    min_stock = models.DecimalField(
        "Scorta minima", max_digits=12, decimal_places=3, default=Decimal("0"),
        help_text="Se la giacenza scende sotto questo valore l'articolo viene evidenziato.",
    )

    tags = models.ManyToManyField(Tag, blank=True, related_name="products", verbose_name="Etichette")
    notes = models.TextField("Note interne", blank=True)
    active = models.BooleanField("Attivo", default=True)

    class Meta:
        verbose_name = "Articolo"
        verbose_name_plural = "Articoli"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["active", "name"], name="product_active_name_idx"),
            models.Index(fields=["barcode"], name="product_barcode_idx"),
        ]

    def __str__(self):
        return f"{self.code} – {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            super().save(*args, **kwargs)
            self.code = f"ART{self.pk:05d}"
            return super().save(update_fields=["code"])
        return super().save(*args, **kwargs)

    # ------------------------------------------------------------ giacenza
    @property
    def total_stock(self):
        cached = getattr(self, "stock_total", None)
        if cached is not None:
            return cached
        return self.stock_levels.aggregate(total=Sum("quantity"))["total"] or Decimal("0")

    @property
    def is_low_stock(self):
        if not self.is_stock_tracked or self.min_stock <= 0:
            return False
        return self.total_stock < self.min_stock

    # ------------------------------------------------------ prezzi fornitore
    def supplier_price(self, supplier):
        """Miglior prezzo effettivo dai listini attivi del fornitore (None se assente)."""
        from apps.purchasing.models import PriceListItem

        today = timezone.localdate()
        items = (
            PriceListItem.objects.filter(
                product=self,
                pricelist__supplier=supplier,
                pricelist__is_active=True,
                pricelist__valid_from__lte=today,
            )
            .filter(Q(pricelist__valid_to__isnull=True) | Q(pricelist__valid_to__gte=today))
            .select_related("pricelist")
        )
        prices = [item.effective_price for item in items]
        return min(prices) if prices else None

    def purchase_unit_price(self, supplier=None):
        """Prezzo di acquisto da usare per gli ordini fornitore."""
        if supplier is not None:
            price = self.supplier_price(supplier)
            if price is not None:
                return price
        return self.purchase_price
