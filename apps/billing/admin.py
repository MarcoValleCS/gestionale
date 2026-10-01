from django.contrib import admin

from .models import (
    DeliveryNote,
    DeliveryNoteLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
    ScannedDocument,
)


class DeliveryNoteLineInline(admin.TabularInline):
    model = DeliveryNoteLine
    extra = 0


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 0


class PurchaseInvoiceLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 0


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "status", "invoiced", "source_order")
    list_filter = ("status", "invoiced")
    search_fields = ("number", "customer__name")
    inlines = [DeliveryNoteLineInline]


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "status", "grand_total", "paid_at")
    list_filter = ("status", "date")
    search_fields = ("number", "customer__name")
    inlines = [SalesInvoiceLineInline]
    readonly_fields = ("subtotal", "vat_total", "grand_total")


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "supplier", "supplier_reference", "status", "grand_total")
    list_filter = ("status", "date")
    search_fields = ("number", "supplier_reference", "supplier__name")
    inlines = [PurchaseInvoiceLineInline]
    readonly_fields = ("subtotal", "vat_total", "grand_total")


@admin.register(ScannedDocument)
class ScannedDocumentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "status", "supplier", "doc_number", "doc_date", "total_amount", "purchase_invoice")
    list_filter = ("status",)
    search_fields = ("original_name", "doc_number", "supplier__name")
