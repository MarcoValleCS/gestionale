"""Viste dell'app core: dashboard, impostazioni e tabelle di base."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.forms import modelformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, RoleRequiredMixin, has_role, role_required

from .forms import (
    BaseBootstrapModelForm,
    BootstrapFormMixin,
    CompanySettingsForm,
    PaymentTermForm,
    TagForm,
    UnitOfMeasureForm,
    VatRateForm,
)
from .models import CompanySettings, NumberSequence, PaymentTerm, Tag, UnitOfMeasure, VatRate


def home(request):
    """Dashboard con i numeri principali."""
    from apps.catalog.models import Product
    from apps.purchasing.models import PurchaseOrder
    from apps.sales.models import Quote, SalesOrder

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
    }
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
