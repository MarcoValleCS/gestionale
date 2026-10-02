"""Viste dell'app core: dashboard, impostazioni e tabelle di base."""
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, has_role, role_required

from .forms import (
    AttachmentForm,
    BaseBootstrapModelForm,
    BootstrapFormMixin,
    CompanySettingsForm,
    PaymentTermForm,
    TagForm,
    UnitOfMeasureForm,
    VatRateForm,
)
from .models import Attachment, CompanySettings, NumberSequence, PaymentTerm, Tag, UnitOfMeasure, VatRate


def home(request):
    """Dashboard: numeri principali, fatturato e marginalità."""
    from apps.catalog.models import Product
    from apps.purchasing.models import PurchaseOrder
    from apps.sales import analytics
    from apps.sales.models import Quote, SalesOrder

    period = request.GET.get("periodo", analytics.PERIOD_YEAR)
    valid_periods = {value for value, _label in analytics.PERIOD_CHOICES}
    if period not in valid_periods:
        period = analytics.PERIOD_YEAR

    stock_sum = Coalesce(
        Sum("stock_levels__quantity"),
        Value(0),
        output_field=DecimalField(max_digits=14, decimal_places=3),
    )
    low_stock_qs = (
        Product.objects.filter(active=True, is_stock_tracked=True, min_stock__gt=0)
        .annotate(stock_total=stock_sum)
        .filter(stock_total__lt=F("min_stock"))
        .select_related("main_supplier", "uom")
        .order_by("name")
    )

    # Riepilogo del periodo: i dettagli per articolo/cliente/fornitore stanno
    # nella pagina «Statistiche», così la dashboard resta leggera.
    stats = analytics.summary(period)

    # Finestra temporale del grafico: 1 / 3 / 6 / 12 mesi, spostabile indietro
    try:
        months = int(request.GET.get("finestra", 12))
    except (TypeError, ValueError):
        months = 12
    if months not in (1, 3, 6, 12):
        months = 12
    try:
        offset = int(request.GET.get("indietro", 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, min(offset, 36))
    series = analytics.monthly_series(months, end_offset=offset)

    from apps.inventory.models import StockLevel
    from apps.jobs.models import Job, MaintenancePlan
    from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice

    inventory_value = (
        StockLevel.objects.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("product__purchase_price"),
                    output_field=DecimalField(max_digits=16, decimal_places=4),
                )
            )
        )["total"]
        or 0
    )

    invoices_to_collect = SalesInvoice.objects.filter(
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT]
    ).aggregate(total=Sum("grand_total"), count=Count("pk"))
    invoices_to_pay = PurchaseInvoice.objects.filter(status=PurchaseInvoice.STATUS_REGISTERED).aggregate(
        total=Sum("grand_total"), count=Count("pk")
    )

    due_limit = timezone.localdate() + timedelta(days=30)
    maintenance_due_qs = (
        MaintenancePlan.objects.filter(active=True, next_date__lte=due_limit)
        .select_related("customer", "job")
        .order_by("next_date")
    )

    context = {
        "page_title": "Dashboard",
        "quotes_open": Quote.objects.filter(status__in=["draft", "sent"]).count(),
        "orders_open": SalesOrder.objects.exclude(status__in=["delivered", "cancelled"]).count(),
        "po_open": PurchaseOrder.objects.exclude(status__in=["received", "cancelled"]).count(),
        "low_stock_count": low_stock_qs.count(),
        "low_stock": low_stock_qs[:10],
        "recent_quotes": Quote.objects.select_related("customer").order_by("-created_at")[:5],
        "recent_orders": SalesOrder.objects.select_related("customer").order_by("-created_at")[:5],
        "recent_pos": PurchaseOrder.objects.select_related("supplier").order_by("-created_at")[:5],
        # Statistiche
        "period": period,
        "period_choices": analytics.PERIOD_CHOICES,
        "stats": stats,
        "inventory_value": inventory_value,
        # Grafico
        "series": series,
        "months": months,
        "offset": offset,
        "months_choices": (1, 3, 6, 12),
        # Cantieri e assistenza
        "jobs_open": Job.objects.filter(status__in=Job.OPEN_STATUSES).count(),
        "maintenance_due": maintenance_due_qs[:6],
        "maintenance_due_count": maintenance_due_qs.count(),
        # Fatturazione
        "invoices_to_collect": invoices_to_collect,
        "invoices_to_pay": invoices_to_pay,
        "ddt_draft_count": DeliveryNote.objects.filter(status=DeliveryNote.STATUS_DRAFT).count(),
    }

    # Personale: numeri sintetici per la dashboard
    from apps.hr.models import Employee, LeaveRequest, TimeEntry

    today = timezone.localdate()
    context["employees_active"] = Employee.objects.filter(active=True).count()
    context["hours_this_month"] = (
        TimeEntry.objects.filter(date__year=today.year, date__month=today.month).aggregate(total=Sum("hours"))["total"] or 0
    )
    context["leaves_pending"] = LeaveRequest.objects.filter(status=LeaveRequest.STATUS_REQUESTED).count()
    context["leaves_this_month"] = (
        LeaveRequest.objects.filter(
            status=LeaveRequest.STATUS_APPROVED, start_date__lte=today, end_date__gte=today
        )
        .select_related("employee")
        .order_by("start_date")
    )

    return render(request, "core/dashboard.html", context)


@role_required(ROLE_ADMIN)
def settings_home(request):
    return render(request, "core/settings.html", {"page_title": "Impostazioni"})


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ROLE_ADMIN,)


# ------------------------------------------------------------------ Azienda
class CompanyUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = (ROLE_ADMIN,)
    model = CompanySettings
    form_class = CompanySettingsForm
    template_name = "core/company_form.html"
    success_url = reverse_lazy("core:settings")

    def get_object(self, queryset=None):
        return CompanySettings.load()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dati azienda"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Dati azienda aggiornati.")
        return super().form_valid(form)


# ---------------------------------------------------------------------- IVA
class VatRateListView(AdminRequiredMixin, ListView):
    model = VatRate
    template_name = "core/vat_list.html"
    context_object_name = "objects"
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Aliquote IVA"
        return context


class VatRateCreateView(AdminRequiredMixin, CreateView):
    model = VatRate
    form_class = VatRateForm
    template_name = "core/vat_form.html"
    success_url = reverse_lazy("core:vat_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova aliquota IVA"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Aliquota IVA creata.")
        return super().form_valid(form)


class VatRateUpdateView(AdminRequiredMixin, UpdateView):
    model = VatRate
    form_class = VatRateForm
    template_name = "core/vat_form.html"
    success_url = reverse_lazy("core:vat_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica aliquota: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Aliquota IVA aggiornata.")
        return super().form_valid(form)


# --------------------------------------------------------- Unità di misura
class UnitOfMeasureListView(AdminRequiredMixin, ListView):
    model = UnitOfMeasure
    template_name = "core/uom_list.html"
    context_object_name = "objects"
    paginate_by = 100

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Unità di misura"
        return context


class UnitOfMeasureCreateView(AdminRequiredMixin, CreateView):
    model = UnitOfMeasure
    form_class = UnitOfMeasureForm
    template_name = "core/uom_form.html"
    success_url = reverse_lazy("core:uom_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova unità di misura"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Unità di misura creata.")
        return super().form_valid(form)


class UnitOfMeasureUpdateView(AdminRequiredMixin, UpdateView):
    model = UnitOfMeasure
    form_class = UnitOfMeasureForm
    template_name = "core/uom_form.html"
    success_url = reverse_lazy("core:uom_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica unità: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Unità di misura aggiornata.")
        return super().form_valid(form)


# --------------------------------------------------------------- Etichette
class TagListView(AdminRequiredMixin, ListView):
    model = Tag
    template_name = "core/tag_list.html"
    context_object_name = "objects"
    paginate_by = 100

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Etichette"
        return context


class TagCreateView(AdminRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = "core/tag_form.html"
    success_url = reverse_lazy("core:tag_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova etichetta"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Etichetta creata.")
        return super().form_valid(form)


class TagUpdateView(AdminRequiredMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "core/tag_form.html"
    success_url = reverse_lazy("core:tag_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica etichetta: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Etichetta aggiornata.")
        return super().form_valid(form)


# -------------------------------------------------- Condizioni di pagamento
class PaymentTermListView(AdminRequiredMixin, ListView):
    model = PaymentTerm
    template_name = "core/paymentterm_list.html"
    context_object_name = "objects"
    paginate_by = 100

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Condizioni di pagamento"
        return context


class PaymentTermCreateView(AdminRequiredMixin, CreateView):
    model = PaymentTerm
    form_class = PaymentTermForm
    template_name = "core/paymentterm_form.html"
    success_url = reverse_lazy("core:paymentterm_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova condizione di pagamento"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Condizione di pagamento creata.")
        return super().form_valid(form)


class PaymentTermUpdateView(AdminRequiredMixin, UpdateView):
    model = PaymentTerm
    form_class = PaymentTermForm
    template_name = "core/paymentterm_form.html"
    success_url = reverse_lazy("core:paymentterm_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica condizione: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Condizione di pagamento aggiornata.")
        return super().form_valid(form)


# ------------------------------------------------------------- Numerazioni
def sequence_list(request):
    if not has_role(request.user, ROLE_ADMIN):
        raise PermissionDenied("Non hai i permessi necessari per questa operazione.")

    for doc_type, _label in NumberSequence.DOC_TYPE_CHOICES:
        NumberSequence.get_for(doc_type)

    SequenceFormSet = modelformset_factory(
        NumberSequence,
        form=BaseBootstrapModelForm,
        fields=["prefix", "next_number", "padding"],
        extra=0,
    )
    formset = SequenceFormSet(
        request.POST or None,
        queryset=NumberSequence.objects.order_by("doc_type", "year"),
    )
    if request.method == "POST":
        if formset.is_valid():
            formset.save()
            messages.success(request, "Numerazioni aggiornate.")
            return redirect("core:sequence_list")
        messages.error(request, "Controlla i valori inseriti.")

    return render(request, "core/sequence_list.html", {"formset": formset, "page_title": "Numerazioni"})


# --------------------------------------------------------------- allegati
ATTACHMENT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_WAREHOUSE)


def _attachment_redirect(request, product_id=None, job_id=None):
    if product_id:
        return redirect("catalog:product_detail", pk=product_id)
    if job_id:
        return redirect("jobs:job_detail", pk=job_id)
    return redirect("core:home")


@role_required(*ATTACHMENT_ROLES)
def attachment_upload(request):
    if request.method != "POST":
        return redirect("core:home")

    product_id = request.POST.get("product") or None
    job_id = request.POST.get("job") or None
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid() and (product_id or job_id):
        attachment = form.save(commit=False)
        attachment.product_id = product_id
        attachment.job_id = job_id
        attachment.uploaded_by = request.user
        attachment.save()
        messages.success(request, f"Allegato «{attachment.name}» caricato.")
    else:
        messages.error(request, "Caricamento non riuscito: scegli un file valido.")

    return _attachment_redirect(request, product_id, job_id)


@role_required(*ATTACHMENT_ROLES)
def attachment_delete(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk)
    product_id = attachment.product_id
    job_id = attachment.job_id
    if request.method == "POST":
        name = attachment.name
        attachment.file.delete(save=False)
        attachment.delete()
        messages.success(request, f"Allegato «{name}» rimosso.")
    return _attachment_redirect(request, product_id, job_id)


# ------------------------------------------------------- webapp (PWA)
from django.contrib.auth.decorators import login_not_required  # noqa: E402


@login_not_required
def manifest(request):
    """Manifest della webapp (installabile su Android/iPhone)."""
    return render(request, "manifest.webmanifest", content_type="application/manifest+json")


@login_not_required
def service_worker(request):
    """Service worker servito dalla radice per poter controllare tutto il sito."""
    response = render(request, "sw.js", content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, max-age=0"
    return response


@login_not_required
def offline(request):
    return render(request, "core/offline.html")
