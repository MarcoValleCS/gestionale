"""Viste di DDT, fatture emesse e ricevute."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.forms import modelformset_factory
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, has_role, role_required
from apps.core.concurrency import ConflictAwareUpdateView
from apps.contacts.models import Contact
from apps.sales.views import build_print_context, fdate, save_document_lines, with_vat_rates

from . import emailing, pdf, sdi, services
from .forms import (
    DeliveryNoteForm,
    DeliveryNoteLineForm,
    PurchaseInvoiceForm,
    PurchaseInvoiceLineForm,
    SalesInvoiceForm,
    SalesInvoiceLineForm,
)
from .models import (
    DeliveryNote,
    DeliveryNoteLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)

DeliveryNoteLineFormSet = modelformset_factory(DeliveryNoteLine, form=DeliveryNoteLineForm, extra=1, can_delete=True)
SalesInvoiceLineFormSet = modelformset_factory(SalesInvoiceLine, form=SalesInvoiceLineForm, extra=1, can_delete=True)
PurchaseInvoiceLineFormSet = modelformset_factory(PurchaseInvoiceLine, form=PurchaseInvoiceLineForm, extra=1, can_delete=True)

DDT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE)
DDT_VIEW_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_WAREHOUSE, ROLE_PURCHASING)
SALES_INVOICE_ROLES = (ROLE_ADMIN, ROLE_SALES)
PURCHASE_INVOICE_ROLES = (ROLE_ADMIN, ROLE_PURCHASING)


def _fascia_scadenza(giorni):
    """In quale fascia di scadenza cade un documento (giorni di ritardo/attesa)."""
    if giorni < 0:
        return "scadute", "Scadute"
    if giorni <= 30:
        return "entro30", "Entro 30 giorni"
    if giorni <= 60:
        return "entro60", "31-60 giorni"
    if giorni <= 90:
        return "entro90", "61-90 giorni"
    return "oltre90", "Oltre 90 giorni"


@role_required(ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING)
def scadenzario(request):
    """Scadenze di incasso e pagamento, con le fasce di ritardo."""
    oggi = timezone.localdate()
    solo_scadute = request.GET.get("scadute") == "1"

    def riepilogo(queryset, campo_data):
        righe = []
        totali = {"scadute": ZERO, "entro30": ZERO, "entro60": ZERO, "entro90": ZERO, "oltre90": ZERO}
        for documento in queryset:
            scadenza = getattr(documento, campo_data) or documento.date
            giorni = (scadenza - oggi).days
            chiave, etichetta = _fascia_scadenza(giorni)
            righe.append(
                {
                    "documento": documento,
                    "scadenza": scadenza,
                    "giorni": giorni,
                    "fascia": chiave,
                    "fascia_label": etichetta,
                    "scaduto": giorni < 0,
                }
            )
            totali[chiave] += documento.grand_total or ZERO
        righe.sort(key=lambda riga: riga["scadenza"])
        if solo_scadute:
            righe = [riga for riga in righe if riga["scaduto"]]
        return righe, totali

    da_incassare = SalesInvoice.objects.filter(
        status__in=[SalesInvoice.STATUS_ISSUED, SalesInvoice.STATUS_SENT]
    ).select_related("customer")
    da_pagare = PurchaseInvoice.objects.filter(status=PurchaseInvoice.STATUS_REGISTERED).select_related("supplier")

    if not (has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_SALES)):
        da_incassare = SalesInvoice.objects.none()
    if not (has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_PURCHASING)):
        da_pagare = PurchaseInvoice.objects.none()

    righe_incasso, totali_incasso = riepilogo(da_incassare, "due_date")
    righe_pagamento, totali_pagamento = riepilogo(da_pagare, "due_date")

    return render(
        request,
        "billing/scadenzario.html",
        {
            "page_title": "Scadenzario",
            "righe_incasso": righe_incasso,
            "righe_pagamento": righe_pagamento,
            "totali_incasso": totali_incasso,
            "totali_pagamento": totali_pagamento,
            "totale_incasso": sum(totali_incasso.values(), ZERO),
            "totale_pagamento": sum(totali_pagamento.values(), ZERO),
            "totale_scaduto_incasso": totali_incasso["scadute"],
            "totale_scaduto_pagamento": totali_pagamento["scadute"],
            "solo_scadute": solo_scadute,
            "oggi": oggi,
            "email_configurata": emailing.email_configured(),
        },
    )


@role_required(ROLE_ADMIN, ROLE_SALES)
def salesinvoice_reminder(request, pk):
    """Manda un sollecito di pagamento per una fattura scaduta."""
    invoice = get_object_or_404(SalesInvoice.objects.select_related("customer"), pk=pk)
    if request.method != "POST":
        return redirect("billing:scadenzario")

    scadenza = invoice.due_date or invoice.date
    giorni = (timezone.localdate() - scadenza).days
    if not invoice.customer.email:
        messages.error(request, f"Il cliente {invoice.customer.name} non ha un indirizzo email.")
        return redirect("billing:scadenzario")
    if not emailing.email_configured():
        messages.error(request, "Invio email non configurato: imposta le variabili EMAIL_* nel file .env.")
        return redirect("billing:scadenzario")

    oggetto = f"Sollecito fattura {invoice.number}"
    corpo = (
        f"Gentile {invoice.customer.name},\n\n"
        f"ci risulta ancora da saldare la fattura {invoice.number} del {invoice.date:%d/%m/%Y}, "
        f"scaduta il {scadenza:%d/%m/%Y}"
        + (f" ({giorni} giorni fa)" if giorni > 0 else "")
        + f", di importo {invoice.grand_total:.2f} €.\n\n"
        "Se il pagamento è già stato effettuato, la preghiamo di ignorare questo messaggio.\n"
        "Restiamo a disposizione per qualsiasi chiarimento.\n\n"
        "Cordiali saluti"
    )
    try:
        emailing.send_invoice_email(invoice, to_email=invoice.customer.email, subject=oggetto, message=corpo)
    except Exception as exc:
        messages.error(request, f"Sollecito non inviato: {exc}")
    else:
        messages.success(request, f"Sollecito inviato a {invoice.customer.email} per la fattura {invoice.number}.")
    return redirect("billing:scadenzario")


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


class DeliveryNoteUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
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
            context["line_formset"] = DeliveryNoteLineFormSet(prefix="lines", queryset=self.object.lines.select_related("product"))
        context["cancel_url"] = reverse("billing:deliverynote_detail", args=[self.object.pk])
        return with_vat_rates(context, self.object)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = DeliveryNoteLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.select_related("product"))
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
        kind = self.request.GET.get("tipo", "")
        if kind:
            queryset = queryset.filter(kind=kind)
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
        context["kinds"] = SalesInvoice.KIND_CHOICES
        context["customers"] = Contact.objects.filter(is_customer=True, active=True).order_by("name")
        context["status"] = self.request.GET.get("stato", "")
        context["kind"] = self.request.GET.get("tipo", "")
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
        from django.conf import settings as django_settings

        context["email_configured"] = emailing.email_configured()
        context["pdf_available"] = pdf.pdf_available()
        context["sdi_statuses"] = SalesInvoice.SDI_STATUS_CHOICES
        context["sdi_pec_address"] = django_settings.SDI_PEC_ADDRESS
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


class SalesInvoiceUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
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
            context["line_formset"] = SalesInvoiceLineFormSet(prefix="lines", queryset=self.object.lines.select_related("product"))
        context["cancel_url"] = reverse("billing:salesinvoice_detail", args=[self.object.pk])
        context["customer_discounts_json"] = {
            str(contact.pk): str(contact.sale_discount_pct)
            for contact in Contact.objects.filter(is_customer=True, active=True, sale_discount_pct__gt=0)
        }
        return with_vat_rates(context, self.object)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = SalesInvoiceLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.select_related("product"))
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
        from .printing import sales_invoice_print_context

        context.update(sales_invoice_print_context(self.object))
        return context


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_create_from_order(request, pk):
    """Crea una fattura dall'ordine: intera, un acconto (%) oppure il resto."""
    from apps.sales.models import SalesOrder

    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method != "POST":
        return redirect("sales:order_detail", pk=order.pk)
    tipo = request.POST.get("tipo", "")
    try:
        if tipo == "advance":
            percento = _numero_decimale(request.POST.get("percento"))
            if percento is None:
                raise ValidationError("Indica la percentuale dell'acconto.")
            invoice = services.create_order_advance(order, percento, user=request.user)
        elif tipo == "balance":
            invoice = services.create_order_balance(order, user=request.user)
        else:
            only_delivered = request.POST.get("solo_consegnate") == "1"
            invoice = services.create_sales_invoice_from_order(order, user=request.user, only_delivered=only_delivered)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sales:order_detail", pk=order.pk)
    messages.success(request, f"Creata in bozza {invoice.kind_title} ({invoice.number}) dall'ordine {order.number}.")
    if tipo in {"advance", "balance"}:
        return redirect("billing:salesinvoice_update", pk=invoice.pk)
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


def _numero_decimale(valore):
    """Converte un importo/percentuale inserito a mano (virgola o punto)."""
    if valore is None or str(valore).strip() == "":
        return None
    try:
        return Decimal(str(valore).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_create_from_job(request, pk):
    """Crea in bozza un acconto, un SAL o il saldo di un cantiere."""
    from apps.jobs.models import Job

    job = get_object_or_404(Job, pk=pk)
    if request.method != "POST":
        return redirect("jobs:job_detail", pk=job.pk)
    kind = request.POST.get("tipo", "")
    percento = _numero_decimale(request.POST.get("percento"))
    importo = _numero_decimale(request.POST.get("importo"))
    try:
        invoice = services.create_job_invoice(job, kind, percent=percento, amount=importo, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("jobs:job_detail", pk=job.pk)
    messages.success(
        request,
        f"Creata in bozza {invoice.kind_title} ({invoice.number}) per il cantiere {job.name}.",
    )
    return redirect("billing:salesinvoice_update", pk=invoice.pk)


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


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_email(request, pk):
    """Invia la fattura per email (con PDF in allegato se disponibile)."""
    invoice = get_object_or_404(SalesInvoice.objects.select_related("customer"), pk=pk)
    if request.method == "POST":
        to_email = (request.POST.get("to") or invoice.customer.email or "").strip()
        subject = (request.POST.get("subject") or f"Fattura {invoice.number}").strip()
        message_body = (request.POST.get("message") or "").strip()

        if not to_email:
            messages.error(request, "Indica l'indirizzo email del cliente.")
        elif not emailing.email_configured():
            messages.error(request, "Invio email non configurato: imposta le variabili EMAIL_* nel file .env.")
        elif invoice.status == SalesInvoice.STATUS_DRAFT:
            messages.error(request, "Emetti prima la fattura, poi inviala al cliente.")
        else:
            try:
                pdf_attached = emailing.send_invoice_email(invoice, to_email=to_email, subject=subject, message=message_body)
            except Exception as exc:
                messages.error(request, f"Invio non riuscito: {exc}")
            else:
                if invoice.status == SalesInvoice.STATUS_ISSUED:
                    services.mark_sales_invoice_sent(invoice)
                extra = "" if pdf_attached else " (senza allegato PDF: non disponibile su questo sistema)"
                messages.success(request, f"Fattura {invoice.number} inviata a {to_email}{extra}.")
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_sdi_generate(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if request.method == "POST":
        try:
            sdi.save_invoice_xml(invoice)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
        else:
            messages.success(request, f"XML FatturaPA generato per la fattura {invoice.number}.")
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_sdi_download(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if not invoice.xml_file:
        messages.error(request, "Genera prima l'XML della fattura.")
        return redirect("billing:salesinvoice_detail", pk=invoice.pk)
    filename = invoice.xml_file.name.rsplit("/", 1)[-1]
    return FileResponse(invoice.xml_file.open("rb"), as_attachment=True, filename=filename, content_type="application/xml")


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_sdi_send(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if request.method == "POST":
        try:
            sdi.send_invoice_sdi(invoice)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        except Exception as exc:
            messages.error(request, f"Invio allo SDI non riuscito: {exc}")
        else:
            messages.success(
                request,
                f"Fattura {invoice.number} trasmessa allo SDI via PEC. Quando arrivano le ricevute, aggiorna l'esito qui sotto.",
            )
    return redirect("billing:salesinvoice_detail", pk=invoice.pk)


@role_required(*SALES_INVOICE_ROLES)
def salesinvoice_sdi_status(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("sdi_status")
        valid = dict(SalesInvoice.SDI_STATUS_CHOICES)
        if new_status not in valid:
            messages.error(request, "Stato SDI non valido.")
        else:
            invoice.sdi_status = new_status
            invoice.sdi_note = (request.POST.get("sdi_note") or "")[:300]
            invoice.save(update_fields=["sdi_status", "sdi_note", "updated_at"])
            messages.success(request, f"Esito SDI aggiornato: {valid[new_status]}.")
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


class PurchaseInvoiceUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
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
            context["line_formset"] = PurchaseInvoiceLineFormSet(prefix="lines", queryset=self.object.lines.select_related("product"))
        context["cancel_url"] = reverse("billing:purchaseinvoice_detail", args=[self.object.pk])
        return with_vat_rates(context, self.object)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = PurchaseInvoiceLineFormSet(request.POST, prefix="lines", queryset=self.object.lines.select_related("product"))
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


# --------------------------------------------------------------- documenti
# L'acquisizione automatica con OCR è stata rimossa su richiesta: richiedeva
# Tesseract e Poppler, consumava risorse e non era utilizzata. Le fatture
# ricevute si registrano a mano o dagli ordini fornitore ricevuti.

