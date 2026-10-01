from django.contrib import admin

from .models import Quote, QuoteLine, QuoteTemplate, QuoteTemplateLine, SalesOrder, SalesOrderLine


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0


class QuoteTemplateLineInline(admin.TabularInline):
    model = QuoteTemplateLine
    extra = 0


@admin.register(QuoteTemplate)
class QuoteTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "payment_term", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    inlines = [QuoteTemplateLineInline]


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "status", "grand_total")
    list_filter = ("status", "date")
    search_fields = ("number", "customer__name", "reference")
    inlines = [QuoteLineInline]
    readonly_fields = ("subtotal", "vat_total", "grand_total")


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "status", "grand_total")
    list_filter = ("status", "date")
    search_fields = ("number", "customer__name", "reference")
    inlines = [SalesOrderLineInline]
    readonly_fields = ("subtotal", "vat_total", "grand_total")
