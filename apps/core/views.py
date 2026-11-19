"""Viste dell'app core: dashboard, impostazioni e tabelle di base."""
from datetime import datetime, timedelta
from pathlib import Path

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_HR, ROLE_PURCHASING, ROLE_SALES, ROLE_WAREHOUSE, RoleRequiredMixin, has_role, role_required

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
from .cache import memoizza
from .models import Attachment, CompanySettings, InternalMessage, NumberSequence, PaymentTerm, Tag, UnitOfMeasure, VatRate
from .richtext import clean_notes


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
    # Le statistiche costano un giro su tutte le righe consegnate: si tengono in
    # cache per un minuto, tanto i numeri cambiano solo alla consegna di un ordine.
    stats = memoizza(f"analytics_summary_{period}", lambda: analytics.summary(period), 60)

    # I prodotti sotto scorta scorrono tutto il catalogo (23k articoli) con una
    # somma per riga: si tengono in cache per un minuto come le statistiche.
    sotto_scorta = memoizza(
        "sotto_scorta",
        lambda: (low_stock_qs.count(), list(low_stock_qs[:10])),
        60,
    )

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
    series = memoizza(
        f"analytics_serie_{months}_{offset}", lambda: analytics.monthly_series(months, end_offset=offset), 60
    )

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
        "low_stock_count": sotto_scorta[0],
        "low_stock": sotto_scorta[1],
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


@role_required(ROLE_ADMIN)
def email_settings(request):
    """Email di invio predefinita (casella aziendale), stato e prova di invio."""
    from django.conf import settings as dj_settings

    from apps.accounts.models import User

    from .forms import EmailInvioForm
    from .mailing import configurazione_smtp, invia_subito, server_caselle_personali

    azienda = CompanySettings.load()
    form = EmailInvioForm(instance=azienda)
    esito = None
    if request.method == "POST" and request.POST.get("azione") == "salva":
        form = EmailInvioForm(request.POST, instance=azienda)
        if form.is_valid():
            form.save()
            messages.success(request, "Email di invio predefinita aggiornata.")
            return redirect("core:email_settings")
    elif request.method == "POST":
        destinatario = (request.POST.get("to") or request.user.email or "").strip()
        if not destinatario:
            esito = ("errore", "Indica un indirizzo email di destinazione (o aggiungilo al tuo utente).")
        elif not configurazione_smtp()["configurata"]:
            esito = ("errore", "L'invio non è configurato: indica qui sopra la casella di invio (o le variabili EMAIL_* nel file .env).")
        else:
            try:
                invia_subito(
                    to_email=destinatario,
                    subject="Prova di invio dal gestionale",
                    message=(
                        "Questa è una email di prova inviata dal gestionale.\n\n"
                        "Se la ricevi, l'invio di preventivi e fatture funziona."
                    ),
                )
            except Exception as exc:
                esito = ("errore", f"Invio non riuscito: {exc}")
            else:
                esito = ("ok", f"Email di prova inviata a {destinatario} dalla casella aziendale.")

    configurazione = configurazione_smtp()
    utenti = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
    return render(
        request,
        "core/email_settings.html",
        {
            "page_title": "Email",
            "form": form,
            "configurazione": configurazione,
            "password_salvata": bool(azienda.smtp_password),
            "esito": esito,
            "pec_sdi": getattr(dj_settings, "SDI_PEC_ADDRESS", "—"),
            "destinatario": request.user.email,
            "utenti": utenti,
            "server_caselle": server_caselle_personali(azienda),
        },
    )


@role_required(ROLE_ADMIN)
def note_predefinite(request):
    """Testo proposto nelle note dei nuovi preventivi, ordini cliente e ordini fornitore."""
    from .forms import NotePredefiniteForm

    azienda = CompanySettings.load()
    form = NotePredefiniteForm(request.POST or None, instance=azienda)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Note predefinite aggiornate: valgono per i nuovi documenti.")
        return redirect("core:note_predefinite")
    return render(request, "core/note_predefinite.html", {"page_title": "Note predefinite", "form": form})


@role_required(ROLE_ADMIN)
def email_templates_view(request):
    """Editor dei modelli delle email (oggetto e testo) inviati dal gestionale."""
    from .email_templates import DEFAULTS, SEGNAPOSTO
    from .models import EmailTemplate

    if request.method == "POST":
        valori = {}
        mancanti = []
        for kind, etichetta in EmailTemplate.KIND_CHOICES:
            oggetto = (request.POST.get(f"subject_{kind}") or "").strip()
            corpo = (request.POST.get(f"body_{kind}") or "").strip()
            if not oggetto:
                mancanti.append(etichetta)
            valori[kind] = (oggetto, corpo)
        if mancanti:
            messages.error(request, "Oggetto mancante per: " + ", ".join(mancanti) + ".")
        else:
            for kind, (oggetto, corpo) in valori.items():
                EmailTemplate.objects.update_or_create(kind=kind, defaults={"subject": oggetto, "body": corpo})
            messages.success(request, "Modelli email aggiornati.")
        return redirect("core:email_templates")

    modelli = []
    for kind, etichetta in EmailTemplate.KIND_CHOICES:
        modello = EmailTemplate.objects.filter(kind=kind).first()
        default = DEFAULTS.get(kind, {"subject": "", "body": ""})
        modelli.append(
            {
                "kind": kind,
                "label": etichetta,
                "subject": modello.subject if modello else default["subject"],
                "body": modello.body if modello else default["body"],
            }
        )
    return render(
        request,
        "core/email_templates.html",
        {"page_title": "Modelli email", "modelli": modelli, "segna_posto": SEGNAPOSTO},
    )


@role_required(ROLE_ADMIN)
def activity_log(request):
    """Registro delle modifiche: chi ha toccato cosa."""
    from .cache import memoizza
    from .models import ActivityLog

    voci = ActivityLog.objects.select_related("user")
    utente_id = request.GET.get("utente", "")
    if utente_id.isdigit():
        voci = voci.filter(user_id=int(utente_id))
    tipo = request.GET.get("tipo", "")
    if tipo:
        voci = voci.filter(model_name__iexact=tipo)
    azione = request.GET.get("azione", "")
    if azione:
        voci = voci.filter(action=azione)

    totale = voci.count()
    voci = voci[:300]
    # Le tendine dei filtri scorrono tutto il registro: si tengono in cache
    # per 5 minuti (i valori cambiano solo quando si crea un nuovo tipo/utente).
    utenti = memoizza(
        "registro_utenti",
        lambda: list(
            ActivityLog.objects.exclude(user__isnull=True)
            .values_list("user_id", "user__username")
            .distinct()
            .order_by("user__username")
        ),
        300,
    )
    tipi = memoizza(
        "registro_tipi",
        lambda: list(ActivityLog.objects.values_list("model_name", flat=True).distinct().order_by("model_name")),
        300,
    )
    return render(
        request,
        "core/activity.html",
        {
            "page_title": "Registro attività",
            "voci": voci,
            "totale": totale,
            "utenti": utenti,
            "tipi": tipi,
            "azione": azione,
            "tipo": tipo,
            "utente_id": utente_id,
        },
    )


# ------------------------------------------------------------------- guida
def _pagine_visibili(utente):
    """Pagine della guida che questo utente può leggere, in ordine."""
    from .models import WikiPage

    return [pagina for pagina in WikiPage.objects.all() if pagina.visible_to(utente)]


def wiki(request):
    """Guida del gestionale: elenco delle pagine visibili all'utente."""
    pagine = _pagine_visibili(request.user)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        termine = cerca.lower()
        pagine = [
            pagina
            for pagina in pagine
            if termine in pagina.title.lower()
            or termine in pagina.summary.lower()
            or termine in pagina.area.lower()
            or termine in pagina.body.lower()
        ]

    from .guida import ORDINE_AREE

    ordine_aree = {area: posizione for posizione, area in enumerate(ORDINE_AREE)}
    sezioni = {}
    for pagina in sorted(
        pagine,
        key=lambda voce: (ordine_aree.get(voce.area, 999), voce.area, voce.order, voce.title),
    ):
        sezioni.setdefault(pagina.area, []).append(pagina)
    return render(
        request,
        "core/wiki.html",
        {
            "page_title": "Guida",
            "sezioni": sezioni,
            "cerca": cerca,
            "totale": len(pagine),
        },
    )


def wiki_page(request, slug):
    """Una pagina della guida, con l'elenco della sua sezione."""
    from django.http import Http404

    from .models import WikiPage

    pagina = WikiPage.objects.filter(slug=slug).first()
    if pagina is None or not pagina.visible_to(request.user):
        raise Http404("Pagina della guida non trovata.")
    sorelle = [altra for altra in WikiPage.objects.filter(area=pagina.area) if altra.visible_to(request.user)]
    return render(
        request,
        "core/wiki_page.html",
        {
            "page_title": pagina.title,
            "pagina": pagina,
            "sorelle": sorelle,
        },
    )


@role_required(ROLE_ADMIN)
def wiki_edit(request, slug):
    """Modifica di una pagina della guida (solo amministratori)."""
    from .forms import WikiPageForm
    from .models import WikiPage

    pagina = get_object_or_404(WikiPage, slug=slug)
    if request.method == "POST":
        form = WikiPageForm(request.POST, instance=pagina)
        if form.is_valid():
            pagina = form.save(commit=False)
            pagina.updated_by = request.user
            pagina.save()
            messages.success(request, f"Pagina «{pagina.title}» aggiornata.")
            return redirect("core:wiki_page", slug=pagina.slug)
        messages.error(request, "Controlla i campi segnalati.")
    else:
        form = WikiPageForm(instance=pagina)
    return render(
        request,
        "core/wiki_form.html",
        {"page_title": f"Modifica: {pagina.title}", "form": form, "pagina": pagina, "aree": _aree_guida()},
    )


@role_required(ROLE_ADMIN)
def wiki_create(request):
    """Nuova pagina della guida (solo amministratori)."""
    from .forms import WikiPageForm

    if request.method == "POST":
        form = WikiPageForm(request.POST)
        if form.is_valid():
            pagina = form.save(commit=False)
            pagina.updated_by = request.user
            pagina.save()
            messages.success(request, f"Pagina «{pagina.title}» creata.")
            return redirect("core:wiki_page", slug=pagina.slug)
        messages.error(request, "Controlla i campi segnalati.")
    else:
        form = WikiPageForm(initial={"order": 100, "is_published": True})
    return render(
        request,
        "core/wiki_form.html",
        {"page_title": "Nuova pagina della guida", "form": form, "pagina": None, "aree": _aree_guida()},
    )


def _aree_guida():
    from .models import WikiPage

    return sorted({area for area in WikiPage.objects.values_list("area", flat=True).distinct() if area})


# ------------------------------------------------------- copia di sicurezza


def _file_di_backup():
    """Elenco dei backup presenti (i più recenti per primi)."""
    from django.conf import settings as dj_settings

    cartella = Path(dj_settings.BACKUP_ROOT)
    if not cartella.is_dir():
        return []
    voci = []
    for percorso in cartella.glob("*.gz"):
        try:
            info = percorso.stat()
        except OSError:
            continue
        voci.append(
            {
                "nome": percorso.name,
                "byte": info.st_size,
                "quando": datetime.fromtimestamp(info.st_mtime, tz=timezone.get_current_timezone()),
                "database": percorso.name.startswith("db_"),
            }
        )
    voci.sort(key=lambda voce: voce["quando"], reverse=True)
    return voci


@role_required(ROLE_ADMIN)
def backup(request):
    """Copia di sicurezza: elenco dei backup e scaricamento.

    I backup restano sul server: da qui se ne può scaricare una copia su un
    altro computer, così un guasto del server non porta via anche le copie.
    """
    from django.conf import settings as dj_settings

    return render(
        request,
        "core/backup.html",
        {
            "page_title": "Copia di sicurezza",
            "backup": _file_di_backup(),
            "cartella": str(dj_settings.BACKUP_ROOT),
        },
    )


@role_required(ROLE_ADMIN)
def backup_download(request, nome):
    """Scarica un file di backup (solo amministratori, solo dalla cartella)."""
    from django.conf import settings as dj_settings
    from django.http import FileResponse, Http404

    cartella = Path(dj_settings.BACKUP_ROOT).resolve()
    percorso = (cartella / Path(nome).name).resolve()
    # niente percorsi costruiti a mano: si scarica solo un file della cartella
    if percorso.parent != cartella or not percorso.is_file():
        raise Http404("Backup non trovato.")
    return FileResponse(percorso.open("rb"), as_attachment=True, filename=percorso.name, content_type="application/gzip")


# ------------------------------------------------------- messaggi interni
def _utenti_scrivibili(utente):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(is_active=True).exclude(pk=utente.pk).order_by("first_name", "username")


def messaggi(request):
    """Bacheca dei messaggi interni: conversazioni con gli altri utenti."""
    from django.db.models import Q

    from .models import InternalMessage

    if request.method == "POST":
        destinatario_id = request.POST.get("recipient") or ""
        testo = (request.POST.get("body") or "").strip()
        destinatario = _utenti_scrivibili(request.user).filter(pk=destinatario_id).first() if destinatario_id.isdigit() else None
        if destinatario is None:
            messages.error(request, "Scegli a chi mandare il messaggio.")
        elif not testo:
            messages.error(request, "Scrivi il testo del messaggio.")
        else:
            InternalMessage.objects.create(sender=request.user, recipient=destinatario, body=testo)
            return redirect("core:conversazione", pk=destinatario.pk)

    scambiati = (
        InternalMessage.objects.filter(Q(sender=request.user) | Q(recipient=request.user))
        .select_related("sender", "recipient")
        .order_by("created_at", "pk")
    )
    conversazioni = {}
    for messaggio in scambiati:
        altro = messaggio.recipient if messaggio.sender_id == request.user.pk else messaggio.sender
        voce = conversazioni.setdefault(
            altro.pk, {"utente": altro, "ultimo": messaggio, "totale": 0, "non_letti": 0}
        )
        voce["ultimo"] = messaggio
        voce["totale"] += 1
        if messaggio.recipient_id == request.user.pk and not messaggio.is_read:
            voce["non_letti"] += 1
    elenco = sorted(conversazioni.values(), key=lambda voce: voce["ultimo"].created_at, reverse=True)

    return render(
        request,
        "core/messaggi.html",
        {
            "page_title": "Messaggi",
            "conversazioni": elenco,
            "utenti": _utenti_scrivibili(request.user),
            "non_letti": sum(voce["non_letti"] for voce in elenco),
        },
    )


def conversazione(request, pk):
    """Scambio di messaggi con un utente."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from .models import InternalMessage

    altro = get_object_or_404(get_user_model(), pk=pk, is_active=True)
    if altro.pk == request.user.pk:
        return redirect("core:messaggi")

    if request.method == "POST":
        testo = (request.POST.get("body") or "").strip()
        if testo:
            InternalMessage.objects.create(sender=request.user, recipient=altro, body=testo)
        return redirect("core:conversazione", pk=altro.pk)

    scambio = (
        InternalMessage.objects.filter(
            Q(sender=request.user, recipient=altro) | Q(sender=altro, recipient=request.user)
        )
        .select_related("sender", "recipient")
        .order_by("created_at", "pk")
    )
    da_leggere = [m for m in scambio if m.recipient_id == request.user.pk and not m.is_read]
    if da_leggere:
        # Un solo UPDATE per tutta la conversazione (prima uno per messaggio).
        adesso = timezone.now()
        InternalMessage.objects.filter(pk__in=[m.pk for m in da_leggere], read_at__isnull=True).update(
            read_at=adesso, updated_at=adesso
        )
        for messaggio in da_leggere:
            messaggio.read_at = adesso
        from .cache import dimentica

        dimentica(f"badge_msg_{request.user.pk}")

    return render(
        request,
        "core/conversazione.html",
        {"page_title": f"Messaggi con {altro.get_full_name() or altro.username}", "altro": altro, "messaggi": scambio},
    )


def global_search(request):
    """Ricerca unica: articoli, contatti, documenti e cantieri."""
    from django.db.models import Q

    from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice
    from apps.catalog.models import Product
    from apps.catalog.search import filtro_articoli
    from apps.contacts.models import Contact
    from apps.jobs.models import Job
    from apps.purchasing.models import PurchaseOrder
    from apps.sales.models import Quote, SalesOrder

    testo = (request.GET.get("q") or "").strip()
    risultati = {}
    if len(testo) >= 2:
        risultati["contatti"] = Contact.objects.filter(
            Q(name__icontains=testo) | Q(code__icontains=testo) | Q(vat_number__icontains=testo)
            | Q(city__icontains=testo) | Q(email__icontains=testo)
        ).order_by("name")[:15]

        risultati["articoli"] = (
            Product.objects.filter(filtro_articoli(testo)).select_related("uom").order_by("name")[:15]
        )

        documenti = {}
        if has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_SALES):
            documenti["preventivi"] = Quote.objects.filter(
                Q(number__icontains=testo) | Q(customer__name__icontains=testo) | Q(reference__icontains=testo)
            )
            documenti["fatture"] = SalesInvoice.objects.filter(
                Q(number__icontains=testo) | Q(customer__name__icontains=testo)
            )
        if has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_SALES) or has_role(request.user, ROLE_WAREHOUSE) or has_role(request.user, ROLE_PURCHASING):
            documenti["ordini"] = SalesOrder.objects.filter(
                Q(number__icontains=testo) | Q(customer__name__icontains=testo) | Q(reference__icontains=testo)
            )
        if has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_PURCHASING) or has_role(request.user, ROLE_WAREHOUSE):
            documenti["ordini_fornitore"] = PurchaseOrder.objects.filter(
                Q(number__icontains=testo) | Q(supplier__name__icontains=testo)
            )
        if has_role(request.user, ROLE_ADMIN) or has_role(request.user, ROLE_PURCHASING):
            documenti["fatture_ricevute"] = PurchaseInvoice.objects.filter(
                Q(number__icontains=testo) | Q(supplier__name__icontains=testo)
                | Q(supplier_reference__icontains=testo)
            )
        documenti["ddt"] = DeliveryNote.objects.filter(
            Q(number__icontains=testo) | Q(customer__name__icontains=testo)
        )
        documenti["cantieri"] = Job.objects.filter(
            Q(name__icontains=testo) | Q(code__icontains=testo) | Q(city__icontains=testo)
            | Q(customer__name__icontains=testo)
        )
        for chiave, queryset in documenti.items():
            # ogni modello ha relazioni diverse: si carica solo quello che esiste
            campi_modello = {campo.name for campo in queryset.model._meta.get_fields()}
            da_caricare = [campo for campo in ("customer", "supplier") if campo in campi_modello]
            trovati = list(queryset.select_related(*da_caricare)[:10])
            if trovati:
                risultati[chiave] = trovati

    return render(
        request,
        "core/search.html",
        {"page_title": f"Ricerca: {testo}" if testo else "Ricerca", "testo": testo, "risultati": risultati},
    )


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


@login_not_required
def termini_vendita(request):
    """Condizioni generali di vendita: pagina pubblica, senza login."""
    from apps.core.models import CompanySettings

    company = CompanySettings.load()
    return render(
        request,
        "core/termini.html",
        {"page_title": "Condizioni generali di vendita", "company": company, "termini": company.get_sales_terms()},
    )
