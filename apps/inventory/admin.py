from django.contrib import admin

from .models import StockLevel, StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_default", "active")


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "quantity", "updated_at")
    search_fields = ("product__code", "product__name")
    list_filter = ("warehouse",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "movement_type", "quantity", "warehouse", "reference", "created_by")
    list_filter = ("movement_type", "warehouse")
    search_fields = ("product__code", "product__name", "reference")
    date_hierarchy = "created_at"
