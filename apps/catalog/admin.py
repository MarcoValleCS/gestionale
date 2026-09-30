from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "uom", "sale_price", "sale_vat", "is_stock_tracked", "active")
    list_filter = ("category", "is_stock_tracked", "active", "sale_vat")
    search_fields = ("code", "name", "barcode")
    filter_horizontal = ("tags",)
