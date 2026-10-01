from django.contrib import admin

from .models import Collaborator, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry


class TimeEntryInline(admin.TabularInline):
    model = TimeEntry
    extra = 0
    fields = ("date", "hours", "kind", "job", "description", "billable")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("code", "full_name", "qualification", "hired_on", "contract_weekly_hours", "active")
    list_filter = ("active", "qualification")
    search_fields = ("code", "first_name", "last_name", "fiscal_code")
    readonly_fields = ("code",)
    inlines = [TimeEntryInline]


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "employee", "hours", "kind", "job", "billable")
    list_filter = ("kind", "billable", "date")
    search_fields = ("employee__first_name", "employee__last_name", "description")
    date_hierarchy = "date"


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "start_date", "end_date", "hours", "status", "approved_by")
    list_filter = ("kind", "status")
    search_fields = ("employee__first_name", "employee__last_name", "reason")
    date_hierarchy = "start_date"


class CollaboratorTimeEntryInline(admin.TabularInline):
    model = CollaboratorTimeEntry
    extra = 0
    fields = ("date", "hours", "job", "description")


@admin.register(Collaborator)
class CollaboratorAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "specialization", "hourly_rate", "user", "active")
    list_filter = ("active", "specialization")
    search_fields = ("code", "name", "company", "fiscal_code")
    readonly_fields = ("code",)
    inlines = [CollaboratorTimeEntryInline]


@admin.register(CollaboratorTimeEntry)
class CollaboratorTimeEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "collaborator", "hours", "job", "description")
    list_filter = ("date",)
    search_fields = ("collaborator__name", "collaborator__company", "description")
    date_hierarchy = "date"
