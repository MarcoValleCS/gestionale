from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Dati aggiuntivi", {"fields": ("phone",)}),)
    list_display = ("username", "first_name", "last_name", "email", "is_active", "is_staff")
    list_filter = DjangoUserAdmin.list_filter
