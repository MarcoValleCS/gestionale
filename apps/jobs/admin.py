from django.contrib import admin

from .models import Job, MaintenancePlan


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "customer", "status", "city", "manager")
    list_filter = ("status", "customer")
    search_fields = ("code", "name", "city", "customer__name")


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "job", "frequency", "next_date", "active")
    list_filter = ("frequency", "active")
    search_fields = ("name", "customer__name")
