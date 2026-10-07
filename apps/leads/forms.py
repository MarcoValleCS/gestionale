"""Form dei lead e delle fasi."""
from django import forms
from django.contrib.auth import get_user_model

from apps.contacts.models import Contact
from apps.core.forms import BaseBootstrapModelForm

from .models import Lead, LeadStage


class LeadForm(BaseBootstrapModelForm):
    class Meta:
        model = Lead
        fields = [
            "name",
            "contact",
            "phone",
            "email",
            "city",
            "source",
            "stage",
            "owner",
            "estimated_value",
            "next_action",
            "quote",
            "job",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.jobs.models import Job
        from apps.sales.models import Quote

        self.fields["contact"].queryset = Contact.objects.filter(active=True, is_customer=True).order_by("name")
        self.fields["stage"].queryset = LeadStage.objects.all()
        self.fields["owner"].queryset = (
            get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        )
        self.fields["quote"].queryset = Quote.objects.select_related("customer").order_by("-date", "-pk")
        self.fields["job"].queryset = (
            Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name")
        )
        self.fields["contact"].required = False
        self.fields["quote"].required = False
        self.fields["job"].required = False
        self.fields["estimated_value"].required = False
        self.fields["next_action"].required = False


class LeadStageForm(BaseBootstrapModelForm):
    class Meta:
        model = LeadStage
        fields = ["name", "order", "color", "kind"]
