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
from .models import Attachment, CompanySettings, InboundEmail, InternalMessage, NumberSequence, PaymentTerm, Tag, UnitOfMeasure, VatRate
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


@role_required(ROLE_ADMIN)
def email_settings(request):
    """Stato della configurazione email e invio di una email di prova."""
    from django.conf import settings as dj_settings

    from .mailing import email_configured

    esito = None
    if request.method == "POST":
        destinatario = (request.POST.get("to") or request.user.email or "").strip()
        if not destinatario:
            esito = ("errore", "Indica un indirizzo email di destinazione (o aggiungilo al tuo utente).")
        elif not email_configured():
            esito = ("errore", "L'invio non è configurato: compila le variabili EMAIL_* nel file .env e riavvia.")
        else:
            from django.core.mail import send_mail

            try:
                send_mail(
                    subject="Prova di invio dal gestionale",
                    message=(
                        "Questa è una email di prova inviata dal gestionale.\n\n"
                        "Se la ricevi, l'invio di preventivi e fatture funziona."
                    ),
                    from_email=dj_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[destinatario],
                    fail_silently=False,
                )
            except Exception as exc:
                esito = ("errore", f"Invio non riuscito: {exc}")
            else:
                esito = ("ok", f"Email di prova inviata a {destinatario}.")

    configurato = email_configured()
    backend = dj_settings.EMAIL_BACKEND.rsplit(".", 1)[-1]
    return render(
        request,
        "core/email_settings.html",
        {
            "page_title": "Email",
            "configurato": configurato,
            "esito": esito,
            "backend": backend,
            "host": dj_settings.EMAIL_HOST or "—",
            "port": dj_settings.EMAIL_PORT,
            "utente": dj_settings.EMAIL_HOST_USER or "—",
            "mittente": dj_settings.DEFAULT_FROM_EMAIL,
            "tls": getattr(dj_settings, "EMAIL_USE_TLS", False),
            "pec_sdi": getattr(dj_settings, "SDI_PEC_ADDRESS", "—"),
            "destinatario": request.user.email,
        },
    )


@role_required(ROLE_ADMIN)
def activity_log(request):
    """Registro delle modifiche: chi ha toccato cosa."""
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
    utenti = (
        ActivityLog.objects.exclude(user__isnull=True)
        .values_list("user_id", "user__username")
        .distinct()
        .order_by("user__username")
    )
    tipi = ActivityLog.objects.values_list("model_name", flat=True).distinct().order_by("model_name")
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
    for messaggio in da_leggere:
        messaggio.mark_read()

    return render(
        request,
        "core/conversazione.html",
        {"page_title": f"Messaggi con {altro.get_full_name() or altro.username}", "altro": altro, "messaggi": scambio},
    )


# ----------------------------------------------------------- posta in arrivo
POSTA_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING, ROLE_HR)


@role_required(*POSTA_ROLES)
def posta(request):
    """Casella aziendale: elenco delle email ricevute."""
    from django.conf import settings as dj_settings
    from django.db.models import Q

    from .imap import posta_configurata

    elenco = InboundEmail.objects.select_related("contact")
    filtro = request.GET.get("filtro", "rilevanti")
    if filtro == "non_lette":
        elenco = elenco.filter(read_at__isnull=True)
    elif filtro == "allegati":
        elenco = elenco.filter(attachments__isnull=False).exclude(attachments=[])
    elif filtro == "contatti":
        elenco = elenco.filter(contact__isnull=False)
    elif filtro == "rilevanti":
        elenco = elenco.filter(is_relevant=True)
    # filtro vuoto o "tutte": nessun filtro

    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        elenco = elenco.filter(
            Q(subject__icontains=cerca) | Q(sender_email__icontains=cerca) | Q(sender_name__icontains=cerca)
        )

    base = InboundEmail.objects.all()
    from django.db.models import Count, Q

    conteggi = base.aggregate(
        tutte=Count("pk"),
        rilevanti=Count("pk", filter=Q(is_relevant=True)),
        non_lette=Count("pk", filter=Q(read_at__isnull=True)),
        allegati=Count("pk", filter=~Q(attachments=[]) & Q(attachments__isnull=False)),
        contatti=Count("pk", filter=Q(contact__isnull=False)),
    )
    return render(
        request,
        "core/posta.html",
        {
            "page_title": "Posta",
            "email": elenco[:200],
            "totale": elenco.count(),
            "non_lette": conteggi["non_lette"],
            "conteggi": conteggi,
            "filtro": filtro,
            "cerca": cerca,
            "configurata": posta_configurata(),
            "cartella": dj_settings.IMAP_FOLDER,
        },
    )


@role_required(*POSTA_ROLES)
def posta_sincronizza(request):
    """Scarica le nuove email dalla casella.

    Ogni scaricamento apre una connessione al server di posta: se qualcuno
    preme il pulsante più volte di seguito si aspetta, invece di aprire dieci
    connessioni in un minuto.
    """
    from django.core.cache import cache

    from .imap import PostaNonConfigurata, sincronizza

    if request.method == "POST":
        if cache.get("posta_sincronizzazione_in_corso"):
            messages.info(request, "Una sincronizzazione è appena partita: attendi qualche secondo e ricarica.")
            return redirect("core:posta")
        cache.set("posta_sincronizzazione_in_corso", True, 20)
        try:
            esito = sincronizza()
        except PostaNonConfigurata as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Non sono riuscito a leggere la casella: {exc}")
        else:
            if esito["nuove"]:
                messages.success(request, f"{esito['nuove']} nuove email scaricate ({esito['esaminate']} controllate).")
            else:
                messages.info(request, f"Nessuna email nuova ({esito['esaminate']} controllate).")
    return redirect("core:posta")


@role_required(*POSTA_ROLES)
def posta_messaggio(request, pk):
    """Legge una email (scarica il corpo la prima volta)."""
    from .imap import PostaNonConfigurata, scarica_corpo
    from .models import InboundEmail

    email_ricevuta = get_object_or_404(InboundEmail, pk=pk)
    errore = None
    if not email_ricevuta.body_loaded:
        try:
            scarica_corpo(email_ricevuta)
        except PostaNonConfigurata as exc:
            errore = str(exc)
        except Exception as exc:
            errore = f"Non sono riuscito a scaricare il messaggio: {exc}"
    email_ricevuta.mark_read()

    # le immagini incorporate (cid:) si scaricano dal gestionale, così si vedono
    from django.urls import reverse
    from django.utils.safestring import mark_safe

    from .richtext import clean_email_html

    mappa_allegati = {
        allegato["cid"]: reverse("core:posta_allegato", args=[email_ricevuta.pk, allegato["indice"]])
        for allegato in (email_ricevuta.attachments or [])
        if allegato.get("cid")
    }
    allegati_visibili = [a for a in (email_ricevuta.attachments or []) if not a.get("incorporato")]

    return render(
        request,
        "core/posta_messaggio.html",
        {
            "page_title": email_ricevuta.subject,
            "email": email_ricevuta,
            "errore": errore,
            "testo_sicuro": clean_notes(email_ricevuta.body_text),
            # il filtro di nh3 è la barriera di sicurezza: dopo di lui l'HTML
            # può essere mostrato così com'è, altrimenti comparirebbe come testo
            "html_sicuro": mark_safe(clean_email_html(email_ricevuta.body_html, mappa_allegati)),
            "allegati_visibili": allegati_visibili,
        },
    )


@role_required(*POSTA_ROLES)
def posta_rispondi(request, pk):
    """Risponde a una email dalla casella aziendale."""
    from .mailing import email_configured, send_document_email
    from .models import InboundEmail

    email_ricevuta = get_object_or_404(InboundEmail, pk=pk)
    if request.method != "POST":
        return redirect("core:posta_messaggio", pk=pk)

    testo = (request.POST.get("body") or "").strip()
    if not email_ricevuta.sender_email:
        messages.error(request, "Questa email non ha un mittente a cui rispondere.")
    elif not testo:
        messages.error(request, "Scrivi il testo della risposta.")
    elif not email_configured():
        messages.error(request, "Invio email non configurato: imposta le variabili EMAIL_* nel file .env.")
    else:
        oggetto = email_ricevuta.subject
        if not oggetto.lower().startswith("re:"):
            oggetto = f"Re: {oggetto}"
        try:
            send_document_email(to_email=email_ricevuta.sender_email, subject=oggetto, message=testo)
        except Exception as exc:
            messages.error(request, f"Risposta non inviata: {exc}")
        else:
            messages.success(request, f"Risposta inviata a {email_ricevuta.sender_email}.")
    return redirect("core:posta_messaggio", pk=pk)


@role_required(*POSTA_ROLES)
def posta_allegato(request, pk, indice):
    """Scarica un allegato dell'email."""
    from django.http import FileResponse, Http404

    from .imap import PostaNonConfigurata, scarica_allegato
    from .models import InboundEmail

    email_ricevuta = get_object_or_404(InboundEmail, pk=pk)
    try:
        nome, tipo, contenuto = scarica_allegato(email_ricevuta, indice)
    except PostaNonConfigurata as exc:
        messages.error(request, str(exc))
        return redirect("core:posta_messaggio", pk=pk)
    except Exception as exc:
        raise Http404(f"Allegato non disponibile: {exc}")

    from io import BytesIO

    # Lo scaricamento (as_attachment) evita che un allegato pericoloso venga
    # aperto come pagina web nella sessione di chi lo riceve.
    return FileResponse(BytesIO(contenuto), as_attachment=True, filename=nome, content_type=tipo or "application/octet-stream")


def global_search(request):
    """Ricerca unica: articoli, contatti, documenti e cantieri."""
    from django.db.models import Q

    from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice
    from apps.catalog.models import Product
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

        risultati["articoli"] = Product.objects.filter(
            Q(name__icontains=testo) | Q(code__icontains=testo) | Q(barcode__icontains=testo)
        ).select_related("uom").order_by("name")[:15]

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
