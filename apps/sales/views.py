"""Viste di vendite: preventivi e ordini cliente."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, role_required
from apps.contacts.models import Contact
from apps.core.models import VatRate

from . import services
from .forms import QuoteForm, QuoteLineForm, SalesOrderForm, SalesOrderLineForm
from .models import Quote, QuoteLine, SalesOrder, SalesOrderLine

QuoteLineFormSet = modelformset_factory(QuoteLine, form=QuoteLineForm, extra=1, can_delete=True)
SalesOrderLineFormSet = modelformset_factory(SalesOrderLine, form=SalesOrderLineForm, extra=1, can_delete=True)

QUOTE_ROLES = (ROLE_ADMIN, ROLE_SALES)
ORDER_VIEW_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE, ROLE_PURCHASING)
ORDER_EDIT_ROLES = (ROLE_ADMIN, ROLE_SALES)
ORDER_DELIVER_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE)


# ------------------------------------------------------------------ helper
def fdate(value):
    return value.strftime("%d/%m/%Y") if value else ""


def build_print_context(
    document,
    *,
    title,
    counterparty,
    meta_rows,
    back_url,
    counterparty_label="Destinatario",
    notes="",
    show_signature=False,
    signature_label="",
):
    """Contesto per il documento stampabile (templates/print/document.html)."""
    return {
        "document": document,
        "document_title": title,
        "counterparty": counterparty,
        "counterparty_label": counterparty_label,
        "meta_rows": meta_rows,
        "back_url": back_url,
        "lines": document.lines.select_related("product", "uom", "vat_rate"),
        "vat_rows": document.vat_breakdown(),
        "notes": notes,
        "show_signature": show_signature,
        "signature_label": signature_label,
    }


def with_vat_rates(context):
    from apps.core.forms import active_units, active_vat_rates

    context["vat_rates_json"] = {str(v.pk): str(v.rate) for v in VatRate.objects.filter(is_active=True)}
    context["quick_uoms"] = active_units()
    context["quick_vats"] = active_vat_rates()
    return context


def save_document_lines(document, formset, fk_field):
    lines = formset.save(commit=False)
    for line in lines:
        setattr(line, fk_field, document)
        line.save()
    for line in formset.deleted_objects:
        line.delete()
    for position, line in enumerate(document.lines.order_by("pk"), start=1):
        if line.position != position:
            line.position = position
            line.save(update_fields=["position"])


# --------------------------------------------------------------- preventivi
class QuoteListView(RoleRequiredMixin, ListView):
    allowed_roles = QUOTE_ROLES
    model = Quote
    template_name = "sales/quote_list.html"
    context_object_name = "quotes"
    paginate_by = 25

    def get_queryset(self):
        queryset = Quote.objects.select_related("customer").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperti":
            queryset = queryset.filter(status__in=[Quote.STATUS_DRAFT, Quote.STATUS_SENT])
        elif status:
            queryset = queryset.filter(status=status)
        customer_id = self.request.GET.get("cliente", "")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(number__icontains=search) | Q(customer__name__icontains=search) | Q(reference__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Preventivi"
        context["statuses"] = Quote.STATUS_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["customer_id"] = self.request.GET.get("cliente", "")
        context["search"] = self.request.GET.get("q", "")
        return context


class QuoteDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = QUOTE_ROLES
    model = Quote
    template_name = "sales/quote_detail.html"
    context_object_name = "quote"

    def get_queryset(self):
        return Quote.objects.select_related("customer", "payment_term", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Preventivo {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom", "vat_rate")
        context["vat_rows"] = self.object.vat_breakdown()
        context["generated_order"] = self.object.generated_order
        return context


class QuoteCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = QUOTE_ROLES
    model = Quote
    form_class = QuoteForm
    template_name = "sales/quote_form.html"

    def get_success_url(self):
        return reverse_lazy("sales:quote_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo preventivo"
        if "line_formset" not in context:
            context["line_formset"] = QuoteLineFormSet(prefix="lines", queryset=QuoteLine.objects.none())
        context["cancel_url"] = reverse("sales:quote_list")
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = QuoteLineFormSet(request.POST, prefix="lines", queryset=QuoteLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "quote")
            self.object.recalculate()
            messages.success(request, f"Preventivo «{self.object.number}» creato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class QuoteUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = QUOTE_ROLES
    model = Quote
    form_class = QuoteForm
    template_name = "sales/quote_form.html"

    def get_success_url(self):
        return reverse_lazy("sales:quote_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica preventivo {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = QuoteLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("sales:quote_detail", args=[self.object.pk])
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = QuoteLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "quote")
            self.object.recalculate()
            messages.success(request, f"Preventivo «{self.object.number}» aggiornato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class QuotePrintView(RoleRequiredMixin, DetailView):
    allowed_roles = QUOTE_ROLES
    model = Quote
    template_name = "print/document.html"
    context_object_name = "quote"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.object
        context.update(
            build_print_context(
                doc,
                title="Preventivo",
                counterparty=doc.customer,
                counterparty_label="Spett.le cliente",
                meta_rows=[
                    ("Data", fdate(doc.date)),
                    ("Valido fino al", fdate(doc.valid_until)),
                    ("Pagamento", doc.payment_term.name if doc.payment_term else ""),
                    ("Vostro riferimento", doc.reference),
                ],
                back_url=reverse("sales:quote_detail", args=[doc.pk]),
                notes=doc.terms_text,
                show_signature=True,
                signature_label="Per accettazione (data e firma)",
            )
        )
        return context


@role_required(*QUOTE_ROLES)
def quote_send(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if quote.status == Quote.STATUS_DRAFT:
        quote.status = Quote.STATUS_SENT
        quote.save(update_fields=["status"])
        messages.success(request, f"Preventivo {quote.number} segnato come inviato.")
    else:
        messages.warning(request, "Il preventivo non è in bozza: stato non modificato.")
    return redirect("sales:quote_detail", pk=quote.pk)


@role_required(*QUOTE_ROLES)
def quote_accept(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if quote.status in {Quote.STATUS_DRAFT, Quote.STATUS_SENT}:
        quote.status = Quote.STATUS_ACCEPTED
        quote.save(update_fields=["status"])
        messages.success(request, f"Preventivo {quote.number} accettato dal cliente.")
    else:
        messages.warning(request, "Il preventivo non può essere accettato nello stato attuale.")
    return redirect("sales:quote_detail", pk=quote.pk)


@role_required(*QUOTE_ROLES)
def quote_reject(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if quote.status in {Quote.STATUS_DRAFT, Quote.STATUS_SENT, Quote.STATUS_ACCEPTED}:
        quote.status = Quote.STATUS_REJECTED
        quote.save(update_fields=["status"])
        messages.info(request, f"Preventivo {quote.number} rifiutato.")
    else:
        messages.warning(request, "Il preventivo non può essere rifiutato nello stato attuale.")
    return redirect("sales:quote_detail", pk=quote.pk)


@role_required(*QUOTE_ROLES)
def quote_convert(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    try:
        order = services.convert_quote_to_order(quote, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:quote_detail", pk=quote.pk)
    messages.success(request, f"Creato l'ordine cliente {order.number} dal preventivo {quote.number}.")
    return redirect("sales:order_detail", pk=order.pk)


@role_required(*QUOTE_ROLES)
def quote_duplicate(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    new = services.duplicate_quote(quote, user=request.user)
    messages.success(request, f"Preventivo duplicato: {new.number}.")
    return redirect("sales:quote_update", pk=new.pk)


@role_required(*QUOTE_ROLES)
def quote_delete(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    if request.method == "POST":
        if quote.generated_orders.exists():
            messages.error(request, "Il preventivo è collegato a un ordine cliente: non può essere eliminato.")
        else:
            number = quote.number
            quote.delete()
            messages.success(request, f"Preventivo {number} eliminato.")
    return redirect("sales:quote_list")


# ----------------------------------------------------------- ordini cliente
class SalesOrderListView(RoleRequiredMixin, ListView):
    allowed_roles = ORDER_VIEW_ROLES
    model = SalesOrder
    template_name = "sales/order_list.html"
    context_object_name = "orders"
    paginate_by = 25

    def get_queryset(self):
        queryset = SalesOrder.objects.select_related("customer").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperti":
            queryset = queryset.filter(status__in=[SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CONFIRMED])
        elif status:
            queryset = queryset.filter(status=status)
        customer_id = self.request.GET.get("cliente", "")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(number__icontains=search) | Q(customer__name__icontains=search) | Q(reference__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Ordini cliente"
        context["statuses"] = SalesOrder.STATUS_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["customer_id"] = self.request.GET.get("cliente", "")
        context["search"] = self.request.GET.get("q", "")
        return context


class SalesOrderDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = ORDER_VIEW_ROLES
    model = SalesOrder
    template_name = "sales/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return SalesOrder.objects.select_related("customer", "payment_term", "created_by", "source_quote")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Ordine {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom", "vat_rate")
        context["vat_rows"] = self.object.vat_breakdown()
        context["purchase_orders"] = self.object.purchase_orders.select_related("supplier").order_by("pk")
        return context


class SalesOrderCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = ORDER_EDIT_ROLES
    model = SalesOrder
    form_class = SalesOrderForm
    template_name = "sales/order_form.html"

    def get_success_url(self):
        return reverse_lazy("sales:order_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo ordine cliente"
        if "line_formset" not in context:
            context["line_formset"] = SalesOrderLineFormSet(prefix="lines", queryset=SalesOrderLine.objects.none())
        context["cancel_url"] = reverse("sales:order_list")
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = SalesOrderLineFormSet(request.POST, prefix="lines", queryset=SalesOrderLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "order")
            self.object.recalculate()
            messages.success(request, f"Ordine «{self.object.number}» creato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class SalesOrderUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = ORDER_EDIT_ROLES
    model = SalesOrder
    form_class = SalesOrderForm
    template_name = "sales/order_form.html"

    def get_success_url(self):
        return reverse_lazy("sales:order_detail", args=[self.object.pk])

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.warning(request, "L'ordine non è modificabile nello stato attuale.")
            return redirect("sales:order_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica ordine {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = SalesOrderLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("sales:order_detail", args=[self.object.pk])
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = SalesOrderLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "order")
            self.object.recalculate()
            messages.success(request, f"Ordine «{self.object.number}» aggiornato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class SalesOrderPrintView(RoleRequiredMixin, DetailView):
    allowed_roles = ORDER_VIEW_ROLES
    model = SalesOrder
    template_name = "print/document.html"
    context_object_name = "order"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.object
        context.update(
            build_print_context(
                doc,
                title="Conferma d'ordine",
                counterparty=doc.customer,
                counterparty_label="Spett.le cliente",
                meta_rows=[
                    ("Data", fdate(doc.date)),
                    ("Consegna prevista", fdate(doc.expected_date)),
                    ("Pagamento", doc.payment_term.name if doc.payment_term else ""),
                    ("Vostro riferimento", doc.reference),
                ],
                back_url=reverse("sales:order_detail", args=[doc.pk]),
                notes=doc.terms_text,
                show_signature=True,
                signature_label="Conferma d'ordine (data e firma)",
            )
        )
        return context


@role_required(*ORDER_EDIT_ROLES)
def order_confirm(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    try:
        result = services.confirm_sales_order(order, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:order_detail", pk=order.pk)

    messages.success(request, f"Ordine {order.number} confermato.")
    purchase_orders = result["purchase_orders"]
    if purchase_orders:
        numbers = ", ".join(po.number for po in purchase_orders)
        messages.info(request, f"Creati {len(purchase_orders)} ordini fornitore per le carenze di magazzino: {numbers}.")
    for product, shortage in result["without_supplier"]:
        messages.warning(
            request,
            f"«{product.name}»: mancano {shortage} e l'articolo non ha un fornitore abituale. "
            "Imposta il fornitore nell'articolo o crea l'ordine fornitore manualmente.",
        )
    return redirect("sales:order_detail", pk=order.pk)


@role_required(*ORDER_DELIVER_ROLES)
def order_deliver(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status == SalesOrder.STATUS_DRAFT:
        messages.warning(request, "Conferma l'ordine prima di registrare la consegna.")
        return redirect("sales:order_detail", pk=order.pk)
    try:
        errors = services.deliver_sales_order(order, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:order_detail", pk=order.pk)

    if errors:
        for error in errors:
            messages.error(request, error)
        messages.warning(request, "Consegna registrata parzialmente: alcune righe non avevano giacenza sufficiente.")
    else:
        messages.success(request, f"Consegna dell'ordine {order.number} registrata e magazzino scaricato.")
    return redirect("sales:order_detail", pk=order.pk)


@role_required(*ORDER_EDIT_ROLES)
def order_cancel(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == "POST":
        try:
            services.cancel_sales_order(order, user=request.user)
            messages.info(request, f"Ordine {order.number} annullato.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("sales:order_detail", pk=order.pk)


@role_required(*ORDER_EDIT_ROLES)
def order_delete(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == "POST":
        if order.status != SalesOrder.STATUS_DRAFT:
            messages.error(request, "Solo gli ordini in bozza possono essere eliminati.")
        else:
            number = order.number
            order.delete()
            messages.success(request, f"Ordine {number} eliminato.")
            return redirect("sales:order_list")
    return redirect("sales:order_detail", pk=order.pk)
