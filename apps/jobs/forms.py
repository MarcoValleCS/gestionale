from django import forms
from django.contrib.auth import get_user_model

from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm
from apps.sales.models import QuoteTemplate

from .models import Job, MaintenancePlan


class JobForm(BaseBootstrapModelForm):
    class Meta:
        model = Job
        fields = [
            "name",
            "customer",
            "status",
            "address",
            "zip_code",
            "city",
            "province",
            "manager",
            "start_date",
            "end_date",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        self.fields["customer"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["manager"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["manager"].label_from_instance = lambda obj: obj.get_full_name() or obj.username


class MaintenancePlanForm(BaseBootstrapModelForm):
    class Meta:
        model = MaintenancePlan
        fields = ["name", "customer", "job", "template", "frequency", "next_date", "notes", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        self.fields["customer"].label_from_instance = lambda obj: f"{obj.name} ({obj.code})"
        self.fields["job"].queryset = Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name")
        self.fields["job"].label_from_instance = lambda obj: f"{obj.code} – {obj.name} ({obj.customer.name})"
        self.fields["template"].queryset = QuoteTemplate.objects.filter(is_active=True).order_by("sort_order", "name")


