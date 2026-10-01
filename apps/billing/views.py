"""Viste di DDT, fatture emesse/ricevute e acquisizione documenti con OCR."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, role_required
from apps.contacts.models import Contact
from apps.sales.views import build_print_context, fdate, save_document_lines, with_vat_rates

from . import ocr, services
from .forms import (
    DeliveryNoteForm,
    DeliveryNoteLineForm,
    PurchaseInvoiceForm,
    PurchaseInvoiceLineForm,
    SalesInvoiceForm,
    SalesInvoiceLineForm,
    ScanUploadForm,
)
from .models import (
    DeliveryNote,
    DeliveryNoteLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
    ScannedDocument,
)

DeliveryNoteLineFormSet = modelformset_factory(DeliveryNoteLine, form=DeliveryNoteLineForm, extra=1, can_delete=True)
SalesInvoiceLineFormSet = modelformset_factory(SalesInvoiceLine, form=SalesInvoiceLineForm, extra=1, can_delete=True)
PurchaseInvoiceLineFormSet = modelformset_factory(PurchaseInvoiceLine, form=PurchaseInvoiceLineForm, extra=1, can_delete=True)

DDT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE)
DDT_VIEW_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE, ROLE_PURCHASING)
SALES_INVOICE_ROLES = (ROLE_ADMIN, ROLE_SALES)
PURCHASE_INVOICE_ROLES = (ROLE_ADMIN, ROLE_PURCHASING)
SCAN_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_WAREHOUSE)


# ---------------------------------------------------------------------- DDT
class DeliveryNoteListView(RoleRequiredMixin, ListView):
    allowed_roles = DDT_VIEW_ROLES
    model = DeliveryNote
    template_name = "billing/deliverynote_list.html"
    context_object_name = "notes"
    paginate_by = 25

    def get_queryset(self):
        queryset = DeliveryNote.objects.select_related("customer", "source_order").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperti":
            queryset = queryset.filter(status=DeliveryNote.STATUS_DRAFT)
        elif status:
            queryset = queryset.filter(status=status)
        customer_id = self.request.GET.get("cliente", "")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(number__icontains=search) | Q(customer__name__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "DDT (documenti di trasporto)"
        context["statuses"] = DeliveryNote.STATUS_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["customer_id"] = self.request.GET.get("cliente", "")
        context["search"] = self.request.GET.get("q", "")
        context["draft_count"] = DeliveryNote.objects.filter(status=DeliveryNote.STATUS_DRAFT).count()
        return context


class DeliveryNoteDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = DDT_VIEW_ROLES
    model = DeliveryNote
    template_name = "billing/deliverynote_detail.html"
    context_object_name = "note"

    def get_queryset(self):
        return DeliveryNote.objects.select_related("customer", "job", "source_order", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"DDT {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom")
        context["invoices"] = self.object.sales_invoices.order_by("-date")
        return context


class DeliveryNoteCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = DDT_ROLES
    model = DeliveryNote
    form_class = DeliveryNoteForm
    template_name = "billing/deliverynote_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:deliverynote_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo DDT"
        if "line_formset" not in context:
            context["line_formset"] = DeliveryNoteLineFormSet(prefix="lines", queryset=DeliveryNoteLine.objects.none())
        context["cancel_url"] = reverse("billing:deliverynote_list")
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = DeliveryNoteLineFormSet(request.POST, prefix="lines", queryset=DeliveryNoteLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "delivery_note")
            messages.success(request, f"DDT «{self.object.number}» creato in bozza.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class DeliveryNoteUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = DDT_ROLES
    model = DeliveryNote
    form_class = DeliveryNoteForm
    template_name = "billing/deliverynote_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:deliverynote_detail", args=[self.object.pk])

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.warning(request, "Il DDT non è modificabile: è già stato emesso.")
            return redirect("billing:deliverynote_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica DDT {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = DeliveryNoteLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("billing:deliverynote_detail", args=[self.object.pk])
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = DeliveryNoteLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "delivery_note")
            messages.success(request, f"DDT «{self.object.number}» aggiornato.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class DeliveryNotePrintView(RoleRequiredMixin, DetailView):
    allowed_roles = DDT_VIEW_ROLES
    model = DeliveryNote
    template_name = "print/document.html"
    context_object_name = "note"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        note = self.object
        context.update(
            build_print_context(
                note,
                title="Documento di trasporto",
                counterparty=note.customer,
                counterparty_label="Destinatario",
                meta_rows=[
                    ("Data", fdate(note.date)),
                    ("Nostro riferimento", note.number),
                    ("Vostro riferimento", note.source_order.reference if note.source_order_id else ""),
                    ("Cantiere", str(note.job) if note.job_id else ""),
                ],
                extra_fields=[
                    ("Causale trasporto", note.transport_reason),
                    ("Vettore", note.carrier),
                    ("N. colli", note.packages if note.packages is not None else ""),
                    ("Peso (kg)", note.weight if note.weight is not None else ""),
                    ("Destinazione", note.destination_address),
                    ("Note", note.notes),
                ],
                back_url=reverse("billing:deliverynote_detail", args=[note.pk]),
                notes="",
                show_signature=True,
                signature_label="Firma del destinatario per ricevuta",
                show_prices=False,
            )
        )
        return context


@role_required(*DDT_ROLES)
def deliverynote_create_from_order(request, pk):
    from apps.sales.models import SalesOrder

    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method != "POST":
        return redirect("sales:order_detail", pk=order.pk)
    try:
        note = services.create_delivery_note_from_order(order, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:order_detail", pk=order.pk)
    messages.success(request, f"Creato il DDT {note.number} in bozza: controllalo e poi emettilo per scaricare il magazzino.")
    return redirect("billing:deliverynote_detail", pk=note.pk)


@role_required(*DDT_ROLES)
def deliverynote_issue(request, pk):
    note = get_object_or_404(DeliveryNote.objects.select_related("source_order"), pk=pk)
    if request.method == "POST":
        try:
            errors = services.issue_delivery_note(note, user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("billing:deliverynote_detail", pk=note.pk)
        if errors:
            for error in errors:
                messages.error(request, error)
            messages.warning(request, "DDT emesso parzialmente: alcune righe non avevano giacenza sufficiente.")
        else:
            messages.success(request, f"DDT {note.number} emesso: magazzino scaricato.")
    return redirect("billing:deliverynote_detail", pk=note.pk)


@role_required(*DDT_ROLES)
def deliverynote_delete(request, pk):
    note = get_object_or_404(DeliveryNote, pk=pk)
    if request.method == "POST":
        if note.status != DeliveryNote.STATUS_DRAFT:
            messages.error(request, "Solo i DDT in bozza possono essere eliminati.")
        else:
            number = note.number
            note.delete()
            messages.success(request, f"DDT {number} eliminato.")
            return redirect("billing:deliverynote_list")
    return redirect("billing:deliverynote_detail", pk=note.pk)


@role_required(*SALES_INVOICE_ROLES)
def deliverynote_invoice(request, pk):
    note = get_object_or_404(DeliveryNote, pk=pk)
    if request.method == "POST":
        try:
            invoice = services.create_sales_invoice_from_delivery_note(note, user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("billing:deliverynote_detail", pk=note.pk)
        messages.success(request, f"Creata la fattura {invoice.number} in bozza dal DDT {note.number}.")
        return redirect("billing:salesinvoice_detail", pk=invoice.pk)
    return redirect("billing:deliverynote_detail", pk=note.pk)


# ----------------------------------------------------------- fatture emesse
class SalesInvoiceListView(RoleRequiredMixin, ListView):
    allowed_roles = SALES_INVOICE_ROLES
    model = SalesInvoice
    template_name = "billing/salesinvoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        queryset = SalesInvoice.objects.select_related("customer").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperte":
            queryset = queryset.filter(status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT])
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
        context["page_title"] = "Fatture emesse"
        context["statuses"] = SalesInvoice.STATUS_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["customer_id"] = self.request.GET.get("cliente", "")
        context["search"] = self.request.GET.get("q", "")
        open_invoices = SalesInvoice.objects.filter(status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT])
        context["open_count"] = open_invoices.count()
        context["open_total"] = open_invoices.aggregate(total=Sum("grand_total"))["total"] or 0
        return context


class SalesInvoiceDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = SALES_INVOICE_ROLES
    model = SalesInvoice
    template_name = "billing/salesinvoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return SalesInvoice.objects.select_related("customer", "job", "source_order", "source_delivery_note", "payment_term", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Fattura {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom", "vat_rate")
        from apps.sales.models import group_lines_by_section

        context["line_groups"] = group_lines_by_section(context["lines"])
        context["vat_rows"] = self.object.vat_breakdown()
        return context


class SalesInvoiceCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = SALES_INVOICE_ROLES
    model = SalesInvoice
    form_class = SalesInvoiceForm
    template_name = "billing/salesinvoice_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:salesinvoice_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova fattura emessa"
        if "line_formset" not in context:
            context["line_formset"] = SalesInvoiceLineFormSet(prefix="lines", queryset=SalesInvoiceLine.objects.none())
        context["cancel_url"] = reverse("billing:salesinvoice_list")
        context["customer_discounts_json"] = {
            str(contact.pk): str(contact.sale_discount_pct)
            for contact in Contact.objects.filter(is_customer=True, active=True, sale_discount_pct__gt=0)
        }
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = SalesInvoiceLineFormSet(request.POST, prefix="lines", queryset=SalesInvoiceLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "invoice")
            self.object.recalculate()
            messages.success(request, f"Fattura «{self.object.number}» creata in bozza.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class SalesInvoiceUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = SALES_INVOICE_ROLES
    model = SalesInvoice
    form_class = SalesInvoiceForm
    template_name = "billing/salesinvoice_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:salesinvoice_detail", args=[self.object.pk])

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.warning(request, "La fattura non è modificabile: è già stata emessa.")
            return redirect("billing:salesinvoice_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica fattura {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = SalesInvoiceLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("billing:salesinvoice_detail", args=[self.object.pk])
        context["customer_discounts_json"] = {
            str(contact.pk): str(contact.sale_discount_pct)
            for contact in Contact.objects.filter(is_customer=True, active=True, sale_discount_pct__gt=0)
        }
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = SalesInvoiceLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "invoice")
            self.object.recalculate()
            messages.success(request, f"Fattura «{self.object.number}» aggiornata.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class SalesInvoicePrintView(RoleRequiredMixin, DetailView):
    allowed_roles = SALES_INVOICE_ROLES
    model = SalesInvoice
    template_name = "print/document.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object
        context.update(
            build_print_context(
                invoice,
                title="Fattura",
                counterparty=invoice.customer,
                counterparty_label="Spett.le cliente",
                meta_rows=[
                    ("Data", fdate(invoice.date)),
                    ("Scadenza", fdate(invoice.due_date)),
                    ("Pagamento", invoice.payment_term.name if invoice.payment_term else ""),
                    ("Vostro riferimento", invoice.reference),
                    ("Cantiere", str(invoice.job) if invoice.job_id else ""),
                ],
                back_url=reverse("billing:salesinvoice_detail", args=[invoice.pk]),
                notes=invoice.notes,
                show_prices=True,
            )
        )
        return context


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_create_from_order(request, pk):
    from apps.sales.models import SalesOrder

    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method != "POST":
        return redirect("sales:order_detail", pk=order.pk)
    only_delivered = request.POST.get("solo_consegnate") == "1"
    try:
        invoice = services.create_sales_invoice_from_order(order, user=request.user, only_delivered=only_delivered)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:order_detail", pk=order.pk)
    messages.success(request, f"Creata la fattura {invoice.number} in bozza dall'ordine {order.number}.")
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


def _salesinvoice_action(request, pk, action, success_message):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if request.method == "POST":
        try:
            action(invoice)
            messages.success(request, success_message.format(number=invoice.number))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_issue(request, pk):
    return _salesinvoice_action(request, pk, services.issue_sales_invoice, "Fattura {number} emessa.")


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_send(request, pk):
    return _salesinvoice_action(request, pk, services.mark_sales_invoice_sent, "Fattura {number} segnata come inviata al cliente.")


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_pay(request, pk):
    return _salesinvoice_action(request, pk, services.mark_sales_invoice_paid, "Fattura {number} segnata come pagata.")


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_delete(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if request.method == "POST":
        if not invoice.is_editable:
            messages.error(request, "Solo le fatture in bozza possono essere eliminate.")
        else:
            number = invoice.number
            invoice.delete()
            messages.success(request, f"Fattura {number} eliminata.")
            return redirect("billing:salesinvoice_list")
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


# --------------------------------------------------------- fatture ricevute
class PurchaseInvoiceListView(RoleRequiredMixin, ListView):
    allowed_roles = PURCHASE_INVOICE_ROLES
    model = PurchaseInvoice
    template_name = "billing/purchaseinvoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        queryset = PurchaseInvoice.objects.select_related("supplier").order_by("-date", "-pk")
        status = self.request.GET.get("stato", "")
        if status == "aperte":
            queryset = queryset.filter(status=PurchaseInvoice.STATUS_REGISTERED)
        elif status:
            queryset = queryset.filter(status=status)
        supplier_id = self.request.GET.get("fornitore", "")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(supplier__name__icontains=search) | Q(supplier_reference__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Fatture ricevute"
        context["statuses"] = PurchaseInvoice.STATUS_CHOICES
        context["suppliers"] = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["supplier_id"] = self.request.GET.get("fornitore", "")
        context["search"] = self.request.GET.get("q", "")
        open_invoices = PurchaseInvoice.objects.filter(status=PurchaseInvoice.STATUS_REGISTERED)
        context["open_count"] = open_invoices.count()
        context["open_total"] = open_invoices.aggregate(total=Sum("grand_total"))["total"] or 0
        return context


class PurchaseInvoiceDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = PURCHASE_INVOICE_ROLES
    model = PurchaseInvoice
    template_name = "billing/purchaseinvoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return PurchaseInvoice.objects.select_related("supplier", "job", "source_po", "payment_term", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Fattura ricevuta {self.object.number}"
        context["lines"] = self.object.lines.select_related("product", "uom", "vat_rate")
        from apps.sales.models import group_lines_by_section

        context["line_groups"] = group_lines_by_section(context["lines"])
        context["vat_rows"] = self.object.vat_breakdown()
        context["scans"] = self.object.scans.all()
        return context


class PurchaseInvoiceCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = PURCHASE_INVOICE_ROLES
    model = PurchaseInvoice
    form_class = PurchaseInvoiceForm
    template_name = "billing/purchaseinvoice_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:purchaseinvoice_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova fattura ricevuta"
        if "line_formset" not in context:
            context["line_formset"] = PurchaseInvoiceLineFormSet(prefix="lines", queryset=PurchaseInvoiceLine.objects.none())
        context["cancel_url"] = reverse("billing:purchaseinvoice_list")
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = PurchaseInvoiceLineFormSet(request.POST, prefix="lines", queryset=PurchaseInvoiceLine.objects.none())
        if form.is_valid() and formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = request.user
            self.object.save()
            save_document_lines(self.object, formset, "invoice")
            self.object.recalculate()
            messages.success(request, f"Fattura ricevuta «{self.object.number}» registrata in bozza.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


class PurchaseInvoiceUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = PURCHASE_INVOICE_ROLES
    model = PurchaseInvoice
    form_class = PurchaseInvoiceForm
    template_name = "billing/purchaseinvoice_form.html"

    def get_success_url(self):
        return reverse_lazy("billing:purchaseinvoice_detail", args=[self.object.pk])

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.warning(request, "La fattura non è modificabile: è già stata registrata.")
            return redirect("billing:purchaseinvoice_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica fattura ricevuta {self.object.number}"
        if "line_formset" not in context:
            context["line_formset"] = PurchaseInvoiceLineFormSet(prefix="lines", queryset=self.object.lines.all())
        context["cancel_url"] = reverse("billing:purchaseinvoice_detail", args=[self.object.pk])
        return with_vat_rates(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = PurchaseInvoiceLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.all())
        if form.is_valid() and formset.is_valid():
            self.object = form.save()
            save_document_lines(self.object, formset, "invoice")
            self.object.recalculate()
            messages.success(request, f"Fattura ricevuta «{self.object.number}» aggiornata.")
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, line_formset=formset))


@role_required(*PURCHASE_INVOICE_ROLES)
def purchaseinvoice_create_from_po(request, pk):
    from apps.purchasing.models import PurchaseOrder

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method != "POST":
        return redirect("purchasing:po_detail", pk=po.pk)
    only_received = request.POST.get("solo_ricevute") == "1"
    try:
        invoice = services.create_purchase_invoice_from_po(po, user=request.user, only_received=only_received)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("purchasing:po_detail", pk=po.pk)
    messages.success(request, f"Registrata la fattura ricevuta {invoice.number} in bozza dall'ordine {po.number}.")
    return redirect("billing:purchaseinvoice_detail", pk=invoice.pk)


def _purchaseinvoice_action(request, pk, action, success_message):
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    if request.method == "POST":
        try:
            action(invoice)
            messages.success(request, success_message.format(number=invoice.number))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("billing:purchaseinvoice_detail", pk=invoice.pk)


@role_required(*PURCHASE_INVOICE_ROLES)
def purchaseinvoice_register(request, pk):
    return _purchaseinvoice_action(request, pk, services.register_purchase_invoice, "Fattura {number} registrata come da pagare.")


@role_required(*PURCHASE_INVOICE_ROLES)
def purchaseinvoice_pay(request, pk):
    return _purchaseinvoice_action(request, pk, services.mark_purchase_invoice_paid, "Fattura {number} segnata come pagata.")


@role_required(*PURCHASE_INVOICE_ROLES)
def purchaseinvoice_delete(request, pk):
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    if request.method == "POST":
        if not invoice.is_editable:
            messages.error(request, "Solo le fatture in bozza possono essere eliminate.")
        else:
            number = invoice.number
            invoice.delete()
            messages.success(request, f"Fattura ricevuta {number} eliminata.")
            return redirect("billing:purchaseinvoice_list")
    return redirect("billing:purchaseinvoice_detail", pk=invoice.pk)


# ------------------------------------------------------- acquisizione OCR
class ScanListView(RoleRequiredMixin, ListView):
    allowed_roles = SCAN_ROLES
    model = ScannedDocument
    template_name = "billing/scan_list.html"
    context_object_name = "scans"
    paginate_by = 25

    def get_queryset(self):
        return ScannedDocument.objects.select_related("supplier", "purchase_invoice", "uploaded_by").order_by("-created_at", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Acquisisci documenti (OCR)"
        context["form"] = ScanUploadForm()
        context["ocr_available"] = ocr.ocr_available()
        return context


@role_required(*SCAN_ROLES)
def scan_upload(request):
    if request.method != "POST":
        return redirect("billing:scan_list")
    form = ScanUploadForm(request.POST, request.FILES)
    if form.is_valid():
        scan = ScannedDocument.objects.create(file=form.cleaned_data["file"], uploaded_by=request.user)
        ocr.process_scan(scan)
        if scan.status == ScannedDocument.STATUS_OK:
            messages.success(request, "Documento elaborato: controlla i dati letti e crea la fattura.")
        else:
            messages.warning(request, scan.error_message or "Documento salvato, ma l'OCR non ha prodotto risultati utili.")
        return redirect("billing:scan_detail", pk=scan.pk)
    messages.error(request, "Carica un file valido (foto o PDF).")
    return redirect("billing:scan_list")


class ScanDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = SCAN_ROLES
    model = ScannedDocument
    template_name = "billing/scan_detail.html"
    context_object_name = "scan"

    def get_queryset(self):
        return ScannedDocument.objects.select_related("supplier", "purchase_invoice")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scan = self.object
        context["page_title"] = f"Documento acquisito: {scan.original_name}"
        context["suppliers"] = Contact.objects.filter(is_supplier=True, active=True).order_by("name")
        context["guess_lines"] = ocr.guess_lines(scan.extracted_text) if scan.extracted_text else []
        return context


@role_required(*SCAN_ROLES)
def scan_create_invoice(request, pk):
    scan = get_object_or_404(ScannedDocument, pk=pk)
    if request.method != "POST":
        return redirect("billing:scan_detail", pk=scan.pk)

    supplier_id = request.POST.get("supplier")
    supplier = Contact.objects.filter(pk=supplier_id, is_supplier=True).first()
    if supplier is None:
        messages.error(request, "Scegli il fornitore a cui si riferisce il documento.")
        return redirect("billing:scan_detail", pk=scan.pk)

    document_date = scan.doc_date or timezone.localdate()
    invoice = PurchaseInvoice.objects.create(
        supplier=supplier,
        date=document_date,
        supplier_reference=scan.doc_number,
        notes=f"Creato dal documento acquisito «{scan.original_name}»."
        + (f" Totale letto con OCR: {scan.total_amount} € (da riconciliare)." if scan.total_amount else ""),
        created_by=request.user,
    )
    for position, row in enumerate(ocr.guess_lines(scan.extracted_text), start=1):
        from decimal import Decimal, InvalidOperation

        from apps.core.models import VatRate

        try:
            qty = Decimal(row["qty"])
        except (InvalidOperation, KeyError):
            qty = Decimal("1")
        PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            position=position,
            description=row["description"],
            qty=qty,
            unit_price=Decimal("0"),
            vat_rate=VatRate.default_for_purchase(),
        )
    invoice.recalculate()
    scan.purchase_invoice = invoice
    scan.save(update_fields=["purchase_invoice"])
    messages.success(request, f"Creata la fattura ricevuta {invoice.number} dal documento: completa prezzi e aliquote e poi registrala.")
    return redirect("billing:purchaseinvoice_detail", pk=invoice.pk)


@role_required(*SCAN_ROLES)
def scan_delete(request, pk):
    scan = get_object_or_404(ScannedDocument, pk=pk)
    if request.method == "POST":
        name = scan.original_name
        scan.file.delete(save=False)
        scan.delete()
        messages.success(request, f"Documento «{name}» eliminato.")
        return redirect("billing:scan_list")
    return redirect("billing:scan_detail", pk=scan.pk)
