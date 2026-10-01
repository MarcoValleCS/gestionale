from django.contrib import admin

from .models import Attachment, CompanySettings, NumberSequence, PaymentTerm, Tag, UnitOfMeasure, VatRate


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "job", "uploaded_by", "created_at")
    search_fields = ("name", "product__code", "job__code")


@admin.register(VatRate)
class VatRateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "rate", "is_default_sales", "is_default_purchase", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "description")
    search_fields = ("name",)


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ("name", "days", "end_of_month")


@admin.register(NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("doc_type", "year", "prefix", "next_number", "padding")


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "vat_number", "city")

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()
