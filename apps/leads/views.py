"""Pipeline dei lead: bacheca per fasi, scheda e gestione delle fasi."""
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_SALES, RoleRequiredMixin, role_required
from apps.core.concurrency import ConflictAwareUpdateView

from .forms import LeadForm, LeadStageForm
from .models import Lead, LeadStage

LEAD_ROLES = (ROLE_ADMIN, ROLE_SALES)


def _leads_filtrati(request):
    leads = Lead.objects.select_related("contact", "stage", "owner", "quote", "job")
    ricerca = request.GET.get("q", "").strip()
    if ricerca:
        leads = leads.filter(
            Q(name__icontains=ricerca)
            | Q(contact__name__icontains=ricerca)
            | Q(phone__icontains=ricerca)
            | Q(email__icontains=ricerca)
            | Q(city__icontains=ricerca)
        )
    if request.GET.get("miei") == "1":
        leads = leads.filter(owner=request.user)
    return leads


@role_required(*LEAD_ROLES)
def board(request):
    """Bacheca dei lead: una colonna per fase."""
    leads = list(_leads_filtrati(request))
    stages = list(LeadStage.objects.all())
    colonne = [{"stage": stage, "leads": [lead for lead in leads if lead.stage_id == stage.pk]} for stage in stages]
    aperti = [lead for lead in leads if lead.is_open]
    valore_aperto = sum((lead.estimated_value or Decimal("0") for lead in aperti), Decimal("0"))
    in_ritardo = [lead for lead in aperti if lead.next_action and lead.next_action < timezone.localdate()]
    return render(
        request,
        "leads/board.html",
        {
            "page_title": "Lead",
            "colonne": colonne,
            "stages": stages,
            "aperti": aperti,
            "vinti": [lead for lead in leads if lead.is_won],
            "in_ritardo": in_ritardo,
            "valore_aperto": valore_aperto,
            "oggi": timezone.localdate(),
            "search": request.GET.get("q", ""),
            "solo_miei": request.GET.get("miei") == "1",
        },
    )


class LeadDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = LEAD_ROLES
    model = Lead
    template_name = "leads/lead_detail.html"
    context_object_name = "lead"

    def get_queryset(self):
        return Lead.objects.select_related("contact", "stage", "owner", "quote", "job", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        context["stages"] = LeadStage.objects.all()
        context["fase_successiva"] = self.object.next_stage()
        context["oggi"] = timezone.localdate()
        return context


class LeadCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = LEAD_ROLES
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"

    def get_success_url(self):
        return reverse_lazy("leads:lead_detail", args=[self.object.pk])

    def get_initial(self):
        initial = super().get_initial()
        initial["stage"] = LeadStage.objects.filter(kind=LeadStage.KIND_OPEN).order_by("order").first() or LeadStage.objects.first()
        initial["owner"] = self.request.user
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo lead"
        context["cancel_url"] = reverse("leads:board")
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if form.instance.owner_id is None:
            form.instance.owner = self.request.user
        messages.success(self.request, f"Lead «{form.instance.name}» creato.")
        return super().form_valid(form)


class LeadUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = LEAD_ROLES
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"

    def get_success_url(self):
        return reverse_lazy("leads:lead_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica lead: {self.object.name}"
        context["cancel_url"] = reverse("leads:lead_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        messages.success(self.request, "Lead aggiornato.")
        return super().form_valid(form)


@role_required(*LEAD_ROLES)
def lead_stage(request, pk):
    """Sposta un lead in un'altra fase (o alla successiva)."""
    lead = get_object_or_404(Lead.objects.select_related("stage"), pk=pk)
    if request.method == "POST":
        scelta = request.POST.get("stage", "")
        if scelta == "avanti":
            nuova = lead.next_stage()
        elif scelta.isdigit():
            nuova = LeadStage.objects.filter(pk=int(scelta)).first()
        else:
            nuova = None
        if nuova is None:
            messages.warning(request, "Nessuna fase successiva disponibile.")
        elif nuova.pk != lead.stage_id:
            lead.stage = nuova
            lead.save(update_fields=["stage", "updated_at"])
            messages.success(request, f"«{lead.name}» spostato in «{nuova.name}».")
        destinazione = request.POST.get("next", "")
        if destinazione.startswith("/"):
            return redirect(destinazione)
    return redirect("leads:lead_detail", pk=lead.pk)


@role_required(*LEAD_ROLES)
def lead_delete(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == "POST":
        nome = lead.name
        lead.delete()
        messages.success(request, f"Lead «{nome}» eliminato.")
        return redirect("leads:board")
    return redirect("leads:lead_detail", pk=lead.pk)


# ------------------------------------------------------- fasi (impostazioni)
class StageListView(RoleRequiredMixin, ListView):
    allowed_roles = (ROLE_ADMIN,)
    model = LeadStage
    template_name = "leads/stage_list.html"
    context_object_name = "objects"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Fasi lead"
        return context


class StageCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = (ROLE_ADMIN,)
    model = LeadStage
    form_class = LeadStageForm
    template_name = "leads/stage_form.html"
    success_url = reverse_lazy("leads:stage_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova fase"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Fase creata.")
        return super().form_valid(form)


class StageUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = (ROLE_ADMIN,)
    model = LeadStage
    form_class = LeadStageForm
    template_name = "leads/stage_form.html"
    success_url = reverse_lazy("leads:stage_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica fase: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Fase aggiornata.")
        return super().form_valid(form)
