"""Viste di acquisti: ordini fornitore e listini."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_WAREHOUSE, RoleRequiredMixin, role_required
from apps.contacts.models import Contact
from apps.core.models import VatRate
from apps.sales.views import build_print_context, fdate, save_document_lines

from . import services
from .forms import (
    PriceListAdjustForm,
    PriceListItemForm,
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    SupplierPriceListForm,
)
from .models import PriceListItem, PurchaseOrder, PurchaseOrderLine, SupplierPriceList

PurchaseOrderLineFormSet = modelformset_factory(PurchaseOrderLine, form=PurchaseOrderLineForm, extra=1, can_delete=True)

PRICELIST_ROLES = (ROLE_ADMIN, ROLE_PURCHASING)
PO_VIEW_ROLES = (ROLE_ADMIN, ROLE_PURCHASING, ROLE_WAREHOUSE)
PO_EDIT_ROLES = (ROLE_ADMIN, ROLE_PURCHASING)
PO_RECEIVE_ROLES = (ROLE_ADMIN, ROLE_PURCHASING, ROLE_WAREHOUSE)


def with_vat_rates(context):
    from apps.core.forms import active_units, active_vat_rates

    context["vat_rates_json"] = {str(v.pk): str(v.rate) for v in VatRate.objects.filter(is_active=True)}
    context["quick_uoms"] = active_units()
    context["quick_vats"] = active_vat_rates()
    return context


# ------------------------------------------------------------------ listini
class PriceListListView(RoleRequiredMixin, ListView):
    allowed_roles = PRICELIST_ROLES
    model = SupplierPriceList
    template_name = "purchasing/pricelist_list.html"
    context_object_name = "pricelists"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            SupplierPriceList.objects.select_related("supplier")
            .annotate(item_count=Count("items"))
            .order_by("supplier__name", "-valid_from")
        )
        supplier_id = self.request.GET.get("fornitore", "")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(supplier__name__icontains=search))
        if self.request.GET.get("inattivi") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Listini fornitori"
        context["suppliers"] = Contact.objects.filter(is_supplier=True).order_by("name")
        context["supplier_id"] = self.request.GET.get("fornitore", "")
        context["search"] = self.request.GET.get("q", "")
        context["show_inactive"] = self.request.GET.get("inattivi") == "1"
        return context


class PriceListCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = PRICELIST_ROLES
    model = SupplierPriceList
    form_class = SupplierPriceListForm
    template_name = "purchasing/pricelist_form.html"

    def get_success_url(self):
        return reverse_lazy("purchasing:pricelist_detail", args=[self.object.pk])

    def get_initial(self):
        initial = super().get_initial()
        supplier_id = self.request.GET.get("fornitore")
        if supplier_id:
            initial["supplier"] = supplier_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo listino fornitore"
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Listino creato.")
        return super().form_valid(form)


class PriceListUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = PRICELIST_ROLES
    model = SupplierPriceList
    form_class = SupplierPriceListForm
    template_name = "purchasing/pricelist_form.html"

    def get_success_url(self):
        return reverse_lazy("purchasing:pricelist_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica listino: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Listino aggiornato.")
        return super().form_valid(form)


class PriceListDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = PRICELIST_ROLES
    model = SupplierPriceList
    template_name = "purchasing/pricelist_detail.html"
    context_object_name = "pricelist"

    def get_queryset(self):
        return SupplierPriceList.objects.select_related("supplier")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = str(self.object)
        context["items"] = self.object.items.select_related("product", "product__uom").order_by("product__name")
        context["adjustments"] = self.object.adjustments.select_related("applied_by")[:10]
        context["item_form"] = PriceListItemForm()
        context["adjust_form"] = PriceListAdjustForm()
        return context


@role_required(*PRICELIST_ROLES)
def pricelist_item_create(request, pk):
    pricelist = get_object_or_404(SupplierPriceList, pk=pk)
    if request.method == "POST":
        form = PriceListItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.pricelist = pricelist
            if pricelist.items.filter(product=item.product).exists():
                messages.error(request, f"«{item.product}» è già presente in questo listino.")
            else:
                item.save()
                messages.success(request, f"Articolo «{item.product}» aggiunto al listino.")
        else:
            messages.error(request, "Controlla i dati dell'articolo da aggiungere.")
    return redirect("purchasing:pricelist_detail", pk=pricelist.pk)


class PriceListItemUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = PRICELIST_ROLES
    model = PriceListItem
    form_class = PriceListItemForm
    template_name = "purchasing/pricelist_item_form.html"
    context_object_name = "item"

    def get_success_url(self):
        return reverse_lazy("purchasing:pricelist_detail", args=[self.object.pricelist_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica voce di listino: {self.object.product}"
        context["pricelist"] = self.object.pricelist
        return context

    def form_valid(self, form):
        messages.success(self.request, "Voce di listino aggiornata.")
        return super().form_valid(form)


@role_required(*PRICELIST_ROLES)
def pricelist_item_delete(request, pk):
    item = get_object_or_404(PriceListItem.objects.select_related("pricelist", "product"), pk=pk)
    if request.method == "POST":
        pricelist_pk = item.pricelist_id
        product_name = str(item.product)
        item.delete()
        messages.success(request, f"«{product_name}» rimosso dal listino.")
        return redirect("purchasing:pricelist_detail", pk=pricelist_pk)
    return redirect("purchasing:pricelist_detail", pk=item.pricelist_id)


@role_required(*PRICELIST_ROLES)
def pricelist_adjust(request, pk):
    pricelist = get_object_or_404(SupplierPriceList, pk=pk)
    if request.method == "POST":
        form = PriceListAdjustForm(request.POST)
        if form.is_valid():
            try:
                adjustment = services.apply_pricelist_adjustment(pricelist, form.cleaned_data["percent"], user=request.user)
                messages.success(
                    request,
                    f"Variazione del {adjustment.percent}% applicata a {adjustment.items_count} articoli del listino.",
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        else:
            messages.error(request, "Variazione percentuale non valida.")
    return redirect("purchasing:pricelist_detail", pk=pricelist.pk)


# ---------------------------------------------------------- ordini fornitore
class PurchaseOrderListView(RoleRequiredMixin, ListView):
    allowed_roles = PO_VIEW_ROLES
    model = PurchaseOrder
    template_name = "purchasing/po_list.html"
    context_object_name = "orders"
    paginate_by = 25

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related("supplier", "source_sales_order").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperti":
            queryset = queryset.exclude(status__in=[PurchaseOrder.STATUS_RECEIVED, PurchaseOrder.STATUS_CANCELLED])
        elif status:
            queryset = queryset.filter(status=status)
        supplier_id = self.request.GET.get("fornitore", "")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(number__icontains=search) | Q(supplier__name__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Ordini fornitore"
        context["statuses"] = PurchaseOrder.STATUS_CHOICES
        context["suppliers"] = Contact.objects.filter(is_supplier=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["supplier_id"] = self.request.GET.get("fornitore", "")
        context["search"] = self.request.GET.get("q", "")
        return context


class PurchaseOrderDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = PO_VIEW_ROLES
    model = PurchaseOrder
    template_name = "purchasing/po_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return PurchaseOrder.objects.select_related("supplier", "source_sales_order", "payment_term", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Ordine fornitore {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom", "vat_rate")
        context["vat_rows"] = self.object.vat_breakdown()
        return context


class PurchaseOrderCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = PO_EDIT_ROLES
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchasing/po_form.html"

    def get_success_url(self):
        return reverse_lazy("purchasing:po_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo ordine fornitore"
        if "line_formset" not in context:
            context["line_formset"] = PurchaseOrderLineFormSet(prefix="lines", queryset=PurchaseOrderLine.objects.none())
        context["cancel_url"] = reverse("purchasing:po_list")
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = PurchaseOrderLineFormSet(request.POST, prefix="lines", queryset=PurchaseOrderLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "po")
            self.object.recalculate()
            messages.success(request, f"Ordine fornitore «{self.object.number}» creato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class PurchaseOrderUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = PO_EDIT_ROLES
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchasing/po_form.html"

    def get_success_url(self):
        return reverse_lazy("purchasing:po_detail", args=[self.object.pk])

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.warning(request, "L'ordine fornitore non è modificabile nello stato attuale.")
            return redirect("purchasing:po_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica ordine fornitore {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = PurchaseOrderLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("purchasing:po_detail", args=[self.object.pk])
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = PurchaseOrderLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "po")
            self.object.recalculate()
            messages.success(request, f"Ordine fornitore «{self.object.number}» aggiornato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class PurchaseOrderPrintView(RoleRequiredMixin, DetailView):
    allowed_roles = PO_VIEW_ROLES
    model = PurchaseOrder
    template_name = "print/document.html"
    context_object_name = "order"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.object
        context.update(
            build_print_context(
                doc,
                title="Ordine fornitore",
                counterparty=doc.supplier,
                counterparty_label="Spett.le fornitore",
                meta_rows=[
                    ("Data", fdate(doc.date)),
                    ("Consegna prevista", fdate(doc.expected_date)),
                    ("Pagamento", doc.payment_term.name if doc.payment_term else ""),
                    ("Nostro riferimento", doc.source_sales_order.number if doc.source_sales_order else doc.number),
                ],
                back_url=reverse("purchasing:po_detail", args=[doc.pk]),
                notes=doc.notes,
                show_signature=False,
            )
        )
        return context


@role_required(*PO_EDIT_ROLES)
def po_send(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status == PurchaseOrder.STATUS_DRAFT:
        order.status = PurchaseOrder.STATUS_SENT
        order.save(update_fields=["status"])
        messages.success(request, f"Ordine {order.number} segnato come inviato al fornitore.")
    else:
        messages.warning(request, "L'ordine non è in bozza: stato non modificato.")
    return redirect("purchasing:po_detail", pk=order.pk)


@role_required(*PO_EDIT_ROLES)
def po_confirm(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status in {PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SENT}:
        order.status = PurchaseOrder.STATUS_CONFIRMED
        order.save(update_fields=["status"])
        messages.success(request, f"Ordine {order.number} confermato dal fornitore.")
    else:
        messages.warning(request, "L'ordine non può essere confermato nello stato attuale.")
    return redirect("purchasing:po_detail", pk=order.pk)


@role_required(*PO_RECEIVE_ROLES)
def po_receive(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    lines = order.lines.select_related("product", "uom")

    if request.method == "POST":
        if not order.can_receive:
            messages.error(request, "L'ordine non può ricevere merce nello stato attuale.")
            return redirect("purchasing:po_detail", pk=order.pk)

        if "receive_all" in request.POST:
            quantities = {str(line.pk): line.qty_remaining for line in lines if line.qty_remaining > 0}
        else:
            quantities = {key.removeprefix("qty_"): value for key, value in request.POST.items() if key.startswith("qty_")}

        received, errors = services.receive_purchase_order(order, quantities, user=request.user)
        for error in errors:
            messages.error(request, error)
        if received:
            messages.success(request, f"Registrata la ricezione di {len(received)} righe per l'ordine {order.number}. Magazzino aggiornato.")
        elif not errors:
            messages.info(request, "Nessuna quantità da ricevere.")
        return redirect("purchasing:po_detail", pk=order.pk)

    return render(request, "purchasing/po_receive.html", {"order": order, "lines": lines, "page_title": f"Ricezione merce {order.number}"})


@role_required(*PO_EDIT_ROLES)
def po_cancel(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        try:
            services.cancel_purchase_order(order, user=request.user)
            messages.info(request, f"Ordine {order.number} annullato.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("purchasing:po_detail", pk=order.pk)


@role_required(*PO_EDIT_ROLES)
def po_delete(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        if order.status != PurchaseOrder.STATUS_DRAFT:
            messages.error(request, "Solo gli ordini in bozza possono essere eliminati.")
        else:
            number = order.number
            order.delete()
            messages.success(request, f"Ordine fornitore {number} eliminato.")
            return redirect("purchasing:po_list")
    return redirect("purchasing:po_detail", pk=order.pk)
