from django.contrib import admin

from .models import Lead, LeadStage


@admin.register(LeadStage)
class LeadStageAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "kind", "color")
    list_editable = ("order",)
    list_filter = ("kind",)
    ordering = ("order", "name")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "stage", "contact", "owner", "estimated_value", "next_action", "created_at")
    list_filter = ("stage", "owner")
    search_fields = ("name", "contact__name", "phone", "email", "city")
    autocomplete_fields = ()
