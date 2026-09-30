from django.contrib import admin

from .models import PriceListAdjustment, PriceListItem, PurchaseOrder, PurchaseOrderLine, SupplierPriceList


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 0


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(SupplierPriceList)
class SupplierPriceListAdmin(admin.ModelAdmin):
    list_display = ("name", "supplier", "valid_from", "valid_to", "is_active")
    list_filter = ("is_active", "supplier")
    search_fields = ("name", "supplier__name")
    inlines = [PriceListItemInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "supplier", "status", "grand_total")
    list_filter = ("status", "date", "supplier")
    search_fields = ("number", "supplier__name")
    inlines = [PurchaseOrderLineInline]
    readonly_fields = ("subtotal", "vat_total", "grand_total")


@admin.register(PriceListAdjustment)
class PriceListAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("pricelist", "percent", "items_count", "applied_by", "applied_at")
