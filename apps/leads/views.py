"""Pipeline dei lead: bacheca per fasi, scheda e gestione delle fasi."""
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
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
def lead_create_quote(request, pk):
    """Crea il preventivo in bozza dal lead e avanza la fase «Preventivo mandato»."""
    lead = get_object_or_404(Lead.objects.select_related("contact", "stage"), pk=pk)
    if request.method != "POST":
        return redirect("leads:lead_detail", pk=lead.pk)
    if lead.quote_id:
        messages.info(request, f"Questo lead ha già il preventivo {lead.quote.number}.")
        return redirect("sales:quote_detail", pk=lead.quote_id)

    from apps.contacts.models import Contact
    from apps.sales.models import Quote

    cliente = lead.contact
    if cliente is None:
        # il lead non ha ancora una scheda contatto: la creiamo dai suoi dati
        cliente = Contact.objects.create(
            name=lead.name[:200],
            is_customer=True,
            phone=lead.phone,
            email=lead.email,
            city=lead.city,
        )
        lead.contact = cliente

    preventivo = Quote.objects.create(
        customer=cliente,
        job=lead.job,
        reference=lead.name[:100],
        created_by=request.user,
    )
    lead.quote = preventivo

    fase_preventivo = LeadStage.objects.filter(on_quote_created=True).order_by("order").first()
    if fase_preventivo and lead.is_open and fase_preventivo.order > lead.stage.order:
        lead.stage = fase_preventivo
        lead.save(update_fields=["stage", "quote", "contact", "updated_at"])
        messages.success(
            request,
            f"Preventivo {preventivo.number} creato in bozza: il lead è passato a «{fase_preventivo.name}».",
        )
    else:
        lead.save(update_fields=["quote", "contact", "updated_at"])
        messages.success(request, f"Preventivo {preventivo.number} creato in bozza.")
    return redirect("sales:quote_update", pk=preventivo.pk)


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


# ------------------------------------------------- lead dal sito web (API)
@csrf_exempt
@require_POST
@login_not_required
def lead_da_sito(request):
    """Riceve un lead dal sito web (POST JSON, autenticato con token).

    La chiama il sito aquaforma.it quando arriva una richiesta dal modulo
    contatti. Il token condiviso viaggia nell'header ``X-Lead-Token`` e si
    configura con la variabile d'ambiente ``LEAD_SITO_TOKEN``: se il token non
    è configurato l'endpoint risponde 503 (chiuso, non aperto).

    Il campo ``external_id`` rende la ricezione idempotente: se la stessa
    richiesta arriva due volte (es. un nuovo tentativo dopo un timeout), il
    lead non viene duplicato.
    """
    atteso = getattr(settings, "LEAD_SITO_TOKEN", "")
    if not atteso:
        return JsonResponse(
            {"ok": False, "errore": "Endpoint non configurato (LEAD_SITO_TOKEN mancante)."},
            status=503,
        )

    ricevuto = request.headers.get("X-Lead-Token", "")
    if not hmac.compare_digest(ricevuto, atteso):
        return JsonResponse({"ok": False, "errore": "Token non valido."}, status=403)

    if len(request.body) > 64 * 1024:
        return JsonResponse({"ok": False, "errore": "Richiesta troppo grande."}, status=413)

    try:
        dati = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "errore": "JSON non valido."}, status=400)
    if not isinstance(dati, dict):
        return JsonResponse({"ok": False, "errore": "Formato non valido."}, status=400)

    nome = str(dati.get("nome", "")).strip()[:150]
    telefono = str(dati.get("telefono", "")).strip()[:40]
    email = str(dati.get("email", "")).strip()[:160]
    if not nome:
        return JsonResponse({"ok": False, "errore": "Il nome è obbligatorio."}, status=422)
    if not telefono and not email:
        return JsonResponse(
            {"ok": False, "errore": "Serve almeno un recapito (telefono o email)."},
            status=422,
        )

    esterno = str(dati.get("external_id", "")).strip()[:64]
    if esterno:
        esistente = Lead.objects.filter(external_id=esterno).first()
        if esistente is not None:
            return JsonResponse({"ok": True, "creato": False, "duplicato": True, "id": esistente.pk})

    fase = LeadStage.objects.filter(kind=LeadStage.KIND_OPEN).order_by("order").first()
    if fase is None:
        fase = LeadStage.objects.order_by("order").first()
    if fase is None:
        return JsonResponse({"ok": False, "errore": "Nessuna fase lead configurata."}, status=500)

    servizio = str(dati.get("servizio", "")).strip()[:80]
    messaggio = str(dati.get("messaggio", "")).strip()[:4000]
    marketing = bool(dati.get("marketing", False))
    provenienza = f"Sito web — {servizio}" if servizio else "Sito web"

    note = [f"Richiesta dal sito aquaforma.it del {timezone.localtime():%d/%m/%Y %H:%M}"]
    if servizio:
        note.append(f"Servizio: {servizio}")
    if messaggio:
        note += ["", "Messaggio:", messaggio]
    note.append(f"Consenso marketing: {'sì' if marketing else 'no'}")
    campagna = dati.get("attribution")
    if isinstance(campagna, dict):
        pezzi = [
            str(campagna.get(chiave, "") or "").strip()
            for chiave in ("source", "medium", "campaign", "content", "term", "gclid", "fbclid")
        ]
        pezzi = [pezzo for pezzo in pezzi if pezzo]
        if pezzi:
            note.append("Campagna: " + " · ".join(pezzi))
    if esterno:
        note.append(f"ID richiesta sito: {esterno}")

    lead = Lead.objects.create(
        name=nome,
        phone=telefono,
        email=email,
        source=provenienza[:80],
        stage=fase,
        next_action=timezone.localdate() + timedelta(days=1),
        notes="\n".join(note),
        external_id=esterno,
    )
    return JsonResponse({"ok": True, "creato": True, "id": lead.pk, "nome": lead.name})
