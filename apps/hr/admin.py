from django.contrib import admin

from .models import Employee, LeaveRequest, TimeEntry


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
