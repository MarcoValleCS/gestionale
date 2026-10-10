from django.contrib import admin

from .models import Category, KitComponent, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)


class KitComponentInline(admin.TabularInline):
    model = KitComponent
    fk_name = "kit"
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "uom", "sale_price", "sale_vat", "is_stock_tracked", "is_kit", "active")
    list_filter = ("category", "is_stock_tracked", "is_kit", "active", "sale_vat")
    search_fields = ("code", "name", "barcode")
    filter_horizontal = ("tags",)
    inlines = [KitComponentInline]
    # Con 23k articoli: pagine piccole e niente query per riga sulle FK.
    list_per_page = 50
    list_select_related = ("category", "uom", "sale_vat")
