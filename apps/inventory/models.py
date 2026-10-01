from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel


class Warehouse(models.Model):
    name = models.CharField("Nome", max_length=100, unique=True)
    code = models.CharField("Codice", max_length=10, unique=True)
    address_note = models.CharField("Note logistiche", max_length=200, blank=True)
    is_default = models.BooleanField("Magazzino predefinito", default=False)
    active = models.BooleanField("Attivo", default=True)

    class Meta:
        verbose_name = "Magazzino"
        verbose_name_plural = "Magazzini"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first() or cls.objects.order_by("pk").first()


class StockLevel(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_levels", verbose_name="Articolo")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stock_levels", verbose_name="Magazzino")
    quantity = models.DecimalField("Quantità", max_digits=12, decimal_places=3, default=Decimal("0"))
    updated_at = models.DateTimeField("Aggiornata il", auto_now=True)

    class Meta:
        verbose_name = "Giacenza"
        verbose_name_plural = "Giacenze"
        constraints = [models.UniqueConstraint(fields=["product", "warehouse"], name="unique_stock_per_product_warehouse")]
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product} @ {self.warehouse}: {self.quantity}"


class StockMovement(models.Model):
    TYPE_LOAD = "load"
    TYPE_UNLOAD = "unload"
    TYPE_ADJUST = "adjust"
    TYPE_CHOICES = [
        (TYPE_LOAD, "Carico"),
        (TYPE_UNLOAD, "Scarico"),
        (TYPE_ADJUST, "Rettifica"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="movements", verbose_name="Articolo")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements", verbose_name="Magazzino")
    movement_type = models.CharField("Tipo", max_length=10, choices=TYPE_CHOICES)
    quantity = models.DecimalField("Quantità", max_digits=12, decimal_places=3, help_text="Positiva per i carichi, negativa per gli scarichi.")
    unit_cost = models.DecimalField("Costo unitario", max_digits=12, decimal_places=4, null=True, blank=True)
    reference = models.CharField("Riferimento", max_length=50, blank=True, help_text="Numero documento collegato")
    note = models.CharField("Note", max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements", verbose_name="Utente"
    )
    created_at = models.DateTimeField("Data", auto_now_add=True)

    class Meta:
        verbose_name = "Movimento di magazzino"
        verbose_name_plural = "Movimenti di magazzino"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["-created_at"], name="movement_created_idx"),
            models.Index(fields=["product", "-created_at"], name="movement_product_idx"),
        ]

    def __str__(self):
        return f"{self.product} {self.quantity:+} ({self.get_movement_type_display()})"
