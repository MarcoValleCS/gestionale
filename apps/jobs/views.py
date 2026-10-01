"""Viste di cantieri, manutenzioni programmate e seriali."""
from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, role_required
from apps.core.concurrency import ConflictAwareUpdateView

from .forms import AssetForm, JobForm, MaintenancePlanForm
from .models import Asset, Job, MaintenancePlan

JOB_EDIT_ROLES = (ROLE_ADMIN, ROLE_SALES)
SERVICE_EDIT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE)


# ----------------------------------------------------------------- cantieri
class JobListView(ListView):
    model = Job
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 25

    def get_queryset(self):
        queryset = Job.objects.select_related("customer", "manager").order_by("-created_at", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperti":
            queryset = queryset.filter(status__in=Job.OPEN_STATUSES)
        elif status:
            queryset = queryset.filter(status=status)
        customer_id = self.request.GET.get("cliente", "")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(city__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.contacts.models import Contact

        context["page_title"] = "Cantieri"
        context["statuses"] = Job.STATUS_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["customer_id"] = self.request.GET.get("cliente", "")
        context["search"] = self.request.GET.get("q", "")
        context["open_count"] = Job.objects.filter(status__in=Job.OPEN_STATUSES).count()
        return context


class JobDetailView(DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return Job.objects.select_related("customer", "manager")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        context["page_title"] = str(job)
        context["quotes"] = job.quotes.select_related("customer").order_by("-date", "-pk")[:30]
        context["orders"] = job.sales_orders.select_related("customer").order_by("-date", "-pk")[:30]
        context["purchase_orders"] = job.purchase_orders.select_related("supplier").order_by("-date", "-pk")[:30]
        context["plans"] = job.maintenance_plans.order_by("next_date")[:20]
        context["assets"] = job.assets.select_related("product").order_by("-created_at")[:30]
        context["attachments"] = job.attachments.select_related("uploaded_by")[:20]
        return context


class JobCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = JOB_EDIT_ROLES
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:job_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo cantiere"
        context["cancel_url"] = reverse("jobs:job_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Cantiere «{form.instance.name}» creato.")
        return super().form_valid(form)


class JobUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = JOB_EDIT_ROLES
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:job_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica cantiere: {self.object}"
        context["cancel_url"] = reverse("jobs:job_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        messages.success(self.request, "Cantiere aggiornato.")
        return super().form_valid(form)


# ----------------------------------------------------- manutenzioni
class MaintenancePlanListView(ListView):
    model = MaintenancePlan
    template_name = "jobs/maintenance_list.html"
    context_object_name = "plans"
    paginate_by = 25

    def get_queryset(self):
        queryset = MaintenancePlan.objects.select_related("customer", "job", "template").order_by("next_date", "name")
        status = self.request.GET.get("stato", "attive")
        if status == "scadenza":
            queryset = queryset.filter(active=True, next_date__lte=timezone.localdate() + timedelta(days=30))
        elif status == "attive":
            queryset = queryset.filter(active=True)
        elif status == "disattive":
            queryset = queryset.filter(active=False)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(customer__name__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Manutenzioni programmate"
        context["status"] = self.request.GET.get("stato", "attive")
        context["search"] = self.request.GET.get("q", "")
        context["due_count"] = sum(1 for plan in MaintenancePlan.objects.filter(active=True) if plan.is_due(30))
        return context


class MaintenancePlanCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = SERVICE_EDIT_ROLES
    model = MaintenancePlan
    form_class = MaintenancePlanForm
    template_name = "jobs/maintenance_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:maintenance_list")

    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get("cliente")
        if customer_id:
            initial["customer"] = customer_id
        job_id = self.request.GET.get("cantiere")
        if job_id:
            initial["job"] = job_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova manutenzione programmata"
        context["cancel_url"] = reverse("jobs:maintenance_list")
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Manutenzione programmata creata.")
        return super().form_valid(form)


class MaintenancePlanUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = SERVICE_EDIT_ROLES
    model = MaintenancePlan
    form_class = MaintenancePlanForm
    template_name = "jobs/maintenance_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:maintenance_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica manutenzione: {self.object}"
        context["cancel_url"] = reverse("jobs:maintenance_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Manutenzione aggiornata.")
        return super().form_valid(form)


@role_required(*SERVICE_EDIT_ROLES)
def maintenance_advance(request, pk):
    """Segna la manutenzione come eseguita e calcola la prossima scadenza."""
    plan = get_object_or_404(MaintenancePlan, pk=pk)
    if request.method == "POST":
        next_date = plan.advance()
        messages.success(request, f"Manutenzione «{plan.name}» eseguita: prossima scadenza {next_date.strftime('%d/%m/%Y')}.")
    return redirect("jobs:maintenance_list")


@role_required(*SERVICE_EDIT_ROLES)
def maintenance_create_quote(request, pk):
    """Genera un preventivo dal piano di manutenzione (con le righe del modello)."""
    plan = get_object_or_404(MaintenancePlan.objects.select_related("customer", "job", "template"), pk=pk)
    if request.method != "POST":
        return redirect("jobs:maintenance_list")

    from apps.sales.models import Quote, QuoteLine

    quote = Quote.objects.create(
        customer=plan.customer,
        job=plan.job,
        payment_term=plan.template.payment_term if plan.template else None,
        reference=f"Manutenzione {plan.name}",
        terms_text=plan.template.terms_text if plan.template else "",
        created_by=request.user,
    )
    if plan.template:
        for line in plan.template.lines.all():
            QuoteLine.objects.create(
                quote=quote,
                position=line.position,
                section=line.section,
                product=line.product,
                description=line.description,
                qty=line.qty,
                uom=line.uom,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                vat_rate=line.vat_rate,
            )
    quote.recalculate()
    messages.success(request, f"Creato il preventivo {quote.number} per «{plan.name}». Controlla e invialo al cliente.")
    return redirect("sales:quote_detail", pk=quote.pk)


@role_required(*SERVICE_EDIT_ROLES)
def maintenance_delete(request, pk):
    plan = get_object_or_404(MaintenancePlan, pk=pk)
    if request.method == "POST":
        name = plan.name
        plan.delete()
        messages.success(request, f"Manutenzione «{name}» eliminata.")
    return redirect("jobs:maintenance_list")


# ----------------------------------------------------------------- seriali
class AssetListView(ListView):
    model = Asset
    template_name = "jobs/asset_list.html"
    context_object_name = "assets"
    paginate_by = 50

    def get_queryset(self):
        queryset = Asset.objects.select_related("product", "customer", "job").order_by("-created_at")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(serial_number__icontains=search)
                | Q(product__name__icontains=search)
                | Q(product__code__icontains=search)
                | Q(customer__name__icontains=search)
            )
        warranty = self.request.GET.get("garanzia", "")
        if warranty == "valida":
            queryset = queryset.filter(installed_on__isnull=False)
            queryset = [asset for asset in queryset if asset.under_warranty]
        elif warranty == "scaduta":
            queryset = queryset.filter(installed_on__isnull=False)
            queryset = [asset for asset in queryset if not asset.under_warranty]
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Seriali installati"
        context["search"] = self.request.GET.get("q", "")
        context["warranty"] = self.request.GET.get("garanzia", "")
        return context


class AssetCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = SERVICE_EDIT_ROLES
    model = Asset
    form_class = AssetForm
    template_name = "jobs/asset_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:asset_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo seriale installato"
        context["cancel_url"] = reverse("jobs:asset_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Seriale registrato.")
        return super().form_valid(form)


class AssetUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = SERVICE_EDIT_ROLES
    model = Asset
    form_class = AssetForm
    template_name = "jobs/asset_form.html"

    def get_success_url(self):
        return reverse_lazy("jobs:asset_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica seriale: {self.object}"
        context["cancel_url"] = reverse("jobs:asset_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Seriale aggiornato.")
        return super().form_valid(form)


@role_required(*SERVICE_EDIT_ROLES)
def asset_delete(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        label = str(asset)
        asset.delete()
        messages.success(request, f"Seriale «{label}» eliminato.")
    return redirect("jobs:asset_list")
