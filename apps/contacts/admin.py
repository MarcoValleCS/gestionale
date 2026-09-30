from django.contrib import admin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_customer", "is_supplier", "city", "vat_number", "active")
    list_filter = ("is_customer", "is_supplier", "active")
    search_fields = ("code", "name", "vat_number", "city", "email")
    filter_horizontal = ("tags",)
