"""Viste di dipendenti, registrazione ore, ferie e registro presenze."""
import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_HR, RoleRequiredMixin, role_required
from apps.core.concurrency import ConflictAwareUpdateView
from apps.core.models import Attachment

from .forms import (
    BulkTimeEntryForm,
    CollaboratorForm,
    CollaboratorPhotoForm,
    CollaboratorTimeEntryForm,
    EmployeeForm,
    RapportinoForm,
    RimandaRapportinoForm,
    SpeseFormSet,
    LeaveRequestForm,
    StandardHoursForm,
    TimeEntryForm,
    active_employees,
)
from .models import Collaborator, CollaboratorExpense, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry

ZERO = Decimal("0")
HR_EDIT_ROLES = (ROLE_ADMIN, ROLE_HR)

# Sigla mostrata nel registro per ciascun tipo di assenza
LEAVE_MARKS = {
    LeaveRequest.KIND_HOLIDAY: "F",
    LeaveRequest.KIND_ROL: "P",
    LeaveRequest.KIND_SICK: "M",
    LeaveRequest.KIND_UNPAID: "N",
    LeaveRequest.KIND_OTHER: "A",
}


def _month_bounds(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first, last


def _parse_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


# --------------------------------------------------------------- dipendenti
class EmployeeListView(RoleRequiredMixin, ListView):
    allowed_roles = HR_EDIT_ROLES
    model = Employee
    template_name = "hr/employee_list.html"
    context_object_name = "employees"
    paginate_by = 25

    def get_queryset(self):
        queryset = Employee.objects.select_related("user").order_by("last_name", "first_name")
        status = self.request.GET.get("stato", "attivi")
        if status == "attivi":
            queryset = queryset.filter(active=True)
        elif status == "cessati":
            queryset = queryset.filter(active=False)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(code__icontains=search)
                | Q(qualification__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dipendenti"
        context["status"] = self.request.GET.get("stato", "attivi")
        context["search"] = self.request.GET.get("q", "")
        context["active_count"] = Employee.objects.filter(active=True).count()
        return context


class EmployeeDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = HR_EDIT_ROLES
    model = Employee
    template_name = "hr/employee_detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return Employee.objects.select_related("user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        today = timezone.localdate()
        year = _parse_int(self.request.GET.get("anno"), today.year, 2000, 2100)

        context["page_title"] = employee.full_name
        context["year"] = year
        context["years"] = [str(number) for number in range(today.year - 3, today.year + 2)]
        context["entries"] = employee.time_entries.select_related("job").order_by("-date", "-pk")[:40]
        context["hours_year"] = employee.hours_between(date(year, 1, 1), date(year, 12, 31))
        context["hours_month"] = employee.hours_in_month(today.year, today.month)
        context["overtime_year"] = employee.hours_between(date(year, 1, 1), date(year, 12, 31), TimeEntry.KIND_OVERTIME)
        context["travel_year"] = employee.hours_between(date(year, 1, 1), date(year, 12, 31), TimeEntry.KIND_TRAVEL)
        context["holiday_used"] = employee.leave_used(year, LeaveRequest.KIND_HOLIDAY)
        context["holiday_balance"] = employee.holiday_balance(year)
        context["rol_used"] = employee.leave_used(year, LeaveRequest.KIND_ROL)
        context["rol_balance"] = employee.rol_balance(year)
        context["sick_used"] = employee.leave_used(year, LeaveRequest.KIND_SICK)
        context["leaves"] = employee.leave_requests.order_by("-start_date", "-pk")[:25]
        context["monthly"] = [
            {
                "month": month,
                "label": calendar.month_abbr[month],
                "hours": employee.hours_in_month(year, month),
            }
            for month in range(1, 13)
        ]
        return context


class EmployeeCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = HR_EDIT_ROLES
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo dipendente"
        context["cancel_url"] = reverse("hr:employee_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Dipendente «{form.instance.full_name}» creato.")
        return super().form_valid(form)


class EmployeeUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = HR_EDIT_ROLES
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica dipendente: {self.object.full_name}"
        context["cancel_url"] = reverse("hr:employee_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        messages.success(self.request, "Dipendente aggiornato.")
        return super().form_valid(form)


@role_required(*HR_EDIT_ROLES)
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        name = employee.full_name
        employee.delete()
        messages.success(request, f"Dipendente «{name}» eliminato con tutte le sue registrazioni.")
        return redirect("hr:employee_list")
    return redirect("hr:employee_detail", pk=employee.pk)


# ---------------------------------------------------------------- ore
class TimeEntryListView(RoleRequiredMixin, ListView):
    allowed_roles = HR_EDIT_ROLES
    model = TimeEntry
    template_name = "hr/timeentry_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        queryset = TimeEntry.objects.select_related("employee", "job", "job__customer", "created_by")
        employee_id = self.request.GET.get("dipendente", "")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        kind = self.request.GET.get("tipo", "")
        if kind:
            queryset = queryset.filter(kind=kind)
        job_id = self.request.GET.get("cantiere", "")
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        today = timezone.localdate()
        year = _parse_int(self.request.GET.get("anno"), today.year, 2000, 2100)
        month = self.request.GET.get("mese", "")
        if month:
            month_number = _parse_int(month, 0, 1, 12)
            if month_number:
                queryset = queryset.filter(date__year=year, date__month=month_number)
        return queryset.order_by("-date", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.jobs.models import Job

        today = timezone.localdate()
        context["page_title"] = "Registrazione ore"
        context["employees"] = Employee.objects.order_by("last_name", "first_name")
        context["jobs"] = Job.objects.select_related("customer").order_by("name")
        context["kinds"] = TimeEntry.KIND_CHOICES
        context["employee_id"] = self.request.GET.get("dipendente", "")
        context["kind"] = self.request.GET.get("tipo", "")
        context["job_id"] = self.request.GET.get("cantiere", "")
        context["year"] = _parse_int(self.request.GET.get("anno"), today.year, 2000, 2100)
        context["month"] = self.request.GET.get("mese", "")
        context["months"] = [(str(number), calendar.month_name[number]) for number in range(1, 13)]
        context["years"] = [str(number) for number in range(today.year - 3, today.year + 2)]
        context["filtered_total"] = self.get_queryset().aggregate(total=Sum("hours"))["total"] or ZERO
        return context


class TimeEntryCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = HR_EDIT_ROLES
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = "hr/timeentry_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:timeentry_list")

    def get_initial(self):
        initial = super().get_initial()
        employee_id = self.request.GET.get("dipendente")
        if employee_id:
            initial["employee"] = employee_id
        job_id = self.request.GET.get("cantiere")
        if job_id:
            initial["job"] = job_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova registrazione ore"
        context["cancel_url"] = reverse("hr:timeentry_list")
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Ore registrate.")
        return super().form_valid(form)


class TimeEntryUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = HR_EDIT_ROLES
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = "hr/timeentry_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:timeentry_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica ore: {self.object}"
        context["cancel_url"] = reverse("hr:timeentry_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Registrazione aggiornata.")
        return super().form_valid(form)


@role_required(*HR_EDIT_ROLES)
def timeentry_delete(request, pk):
    entry = get_object_or_404(TimeEntry, pk=pk)
    if request.method == "POST":
        label = str(entry)
        entry.delete()
        messages.success(request, f"Registrazione «{label}» eliminata.")
    return redirect("hr:timeentry_list")


@role_required(*HR_EDIT_ROLES)
def timeentry_bulk(request):
    """Inserimento rapido: le ore di tutta la squadra in una giornata."""
    employees = list(active_employees())
    if not employees:
        messages.warning(request, "Aggiungi almeno un dipendente attivo prima di registrare le ore.")
        return redirect("hr:employee_create")

    if request.method == "POST":
        form = BulkTimeEntryForm(request.POST, employees=employees)
        if form.is_valid():
            day = form.cleaned_data["date"]
            kind = form.cleaned_data["kind"]
            job = form.cleaned_data["job"]
            description = form.cleaned_data["description"]
            created = 0
            updated = 0
            for employee, hours in form.entries():
                existing = TimeEntry.objects.filter(employee=employee, date=day, kind=kind).first()
                if existing:
                    existing.hours = hours
                    existing.job = job
                    existing.description = description
                    existing.save(update_fields=["hours", "job", "description", "updated_at"])
                    updated += 1
                else:
                    TimeEntry.objects.create(
                        employee=employee,
                        date=day,
                        hours=hours,
                        kind=kind,
                        job=job,
                        description=description,
                        created_by=request.user,
                    )
                    created += 1
            messages.success(
                request,
                f"Giornata {day:%d/%m/%Y}: {created} registrazioni create"
                + (f", {updated} aggiornate." if updated else "."),
            )
            return redirect(f"{reverse('hr:timesheet')}?anno={day.year}&mese={day.month}")
    else:
        form = BulkTimeEntryForm(employees=employees, initial={"date": timezone.localdate()})

    return render(
        request,
        "hr/timeentry_bulk.html",
        {
            "form": form,
            "employees": employees,
            "rows": [
                {"employee": employee, "field": form[BulkTimeEntryForm.hours_field(employee)]}
                for employee in employees
            ],
            "page_title": "Inserimento rapido ore",
        },
    )


@role_required(*HR_EDIT_ROLES)
def timeentry_standard(request):
    """Registra le ore standard di un periodo (es. 8 ore al giorno per un mese)."""
    if request.method == "POST":
        form = StandardHoursForm(request.POST)
        if form.is_valid():
            dipendente = form.cleaned_data["employee"]
            ore = form.cleaned_data["hours"]
            tipo = form.cleaned_data["kind"]
            cantiere = form.cleaned_data["job"]
            descrizione = form.cleaned_data["description"]
            sovrascrivi = form.cleaned_data["overwrite"]
            giorni = form.giorni()

            creati = aggiornati = saltati = 0
            for giorno in giorni:
                esistente = TimeEntry.objects.filter(employee=dipendente, date=giorno, kind=tipo).first()
                if esistente is not None:
                    if not sovrascrivi:
                        saltati += 1
                        continue
                    esistente.hours = ore
                    esistente.job = cantiere
                    esistente.description = descrizione
                    esistente.save(update_fields=["hours", "job", "description", "updated_at"])
                    aggiornati += 1
                else:
                    TimeEntry.objects.create(
                        employee=dipendente,
                        date=giorno,
                        hours=ore,
                        kind=tipo,
                        job=cantiere,
                        description=descrizione,
                        created_by=request.user,
                    )
                    creati += 1

            riepilogo = f"{creati} giornate registrate"
            if aggiornati:
                riepilogo += f", {aggiornati} aggiornate"
            if saltati:
                riepilogo += f", {saltati} già presenti e lasciate com'erano"
            messages.success(request, f"{dipendente.full_name}: {riepilogo}.")
            if giorni:
                return redirect(f"{reverse('hr:timesheet')}?anno={giorni[0].year}&mese={giorni[0].month}")
            return redirect("hr:timeentry_list")
    else:
        oggi = timezone.localdate()
        form = StandardHoursForm(
            initial={
                "start_date": oggi.replace(day=1),
                "end_date": oggi,
            }
        )

    return render(
        request,
        "hr/timeentry_standard.html",
        {"form": form, "page_title": "Ore standard"},
    )


# ---------------------------------------------------------------- ferie
class LeaveListView(RoleRequiredMixin, ListView):
    allowed_roles = HR_EDIT_ROLES
    model = LeaveRequest
    template_name = "hr/leave_list.html"
    context_object_name = "leaves"
    paginate_by = 40

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related("employee", "approved_by")
        employee_id = self.request.GET.get("dipendente", "")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        status = self.request.GET.get("stato", "")
        if status:
            queryset = queryset.filter(status=status)
        kind = self.request.GET.get("tipo", "")
        if kind:
            queryset = queryset.filter(kind=kind)
        today = timezone.localdate()
        year = _parse_int(self.request.GET.get("anno"), today.year, 2000, 2100)
        queryset = queryset.filter(start_date__year__lte=year, end_date__year__gte=year)
        return queryset.order_by("-start_date", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["page_title"] = "Ferie e permessi"
        context["employees"] = Employee.objects.order_by("last_name", "first_name")
        context["statuses"] = LeaveRequest.STATUS_CHOICES
        context["kinds"] = LeaveRequest.KIND_CHOICES
        context["employee_id"] = self.request.GET.get("dipendente", "")
        context["status"] = self.request.GET.get("stato", "")
        context["kind"] = self.request.GET.get("tipo", "")
        context["year"] = _parse_int(self.request.GET.get("anno"), today.year, 2000, 2100)
        context["years"] = [str(number) for number in range(today.year - 3, today.year + 2)]
        context["pending_count"] = LeaveRequest.objects.filter(status=LeaveRequest.STATUS_REQUESTED).count()
        return context


class LeaveCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = HR_EDIT_ROLES
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "hr/leave_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:leave_list")

    def get_initial(self):
        initial = super().get_initial()
        employee_id = self.request.GET.get("dipendente")
        if employee_id:
            initial["employee"] = employee_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuova richiesta di ferie o permesso"
        context["cancel_url"] = reverse("hr:leave_list")
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Richiesta registrata.")
        return super().form_valid(form)


class LeaveUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = HR_EDIT_ROLES
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "hr/leave_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:leave_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica assenza: {self.object}"
        context["cancel_url"] = reverse("hr:leave_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Assenza aggiornata.")
        return super().form_valid(form)


@role_required(*HR_EDIT_ROLES)
def leave_approve(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        leave.approve(request.user)
        messages.success(request, f"{leave.get_kind_display()} di {leave.employee.full_name} approvata ({leave.duration_label}).")
    return redirect(request.POST.get("next") or "hr:leave_list")


@role_required(*HR_EDIT_ROLES)
def leave_reject(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        leave.reject(request.user)
        messages.success(request, f"{leave.get_kind_display()} di {leave.employee.full_name} rifiutata.")
    return redirect(request.POST.get("next") or "hr:leave_list")


@role_required(*HR_EDIT_ROLES)
def leave_delete(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        label = str(leave)
        leave.delete()
        messages.success(request, f"Assenza «{label}» eliminata.")
    return redirect("hr:leave_list")


# ------------------------------------------------------- registro presenze
def timesheet(request):
    """Registro mensile: ore e assenze di ogni dipendente, giorno per giorno."""
    today = timezone.localdate()
    year = _parse_int(request.GET.get("anno"), today.year, 2000, 2100)
    month = _parse_int(request.GET.get("mese"), today.month, 1, 12)
    first, last = _month_bounds(year, month)

    employees = list(Employee.objects.filter(active=True).order_by("last_name", "first_name"))
    entries = TimeEntry.objects.filter(date__gte=first, date__lte=last).select_related("employee")

    hours_by_cell = defaultdict(lambda: ZERO)
    for entry in entries:
        hours_by_cell[(entry.employee_id, entry.date.day)] += entry.hours

    leave_requests = LeaveRequest.objects.filter(
        status=LeaveRequest.STATUS_APPROVED, start_date__lte=last, end_date__gte=first
    ).select_related("employee")
    leave_by_cell = {}
    for leave in leave_requests:
        start = max(leave.start_date, first)
        end = min(leave.end_date, last)
        current = start
        while current <= end:
            leave_by_cell[(leave.employee_id, current.day)] = LEAVE_MARKS.get(leave.kind, "A")
            current += timedelta(days=1)

    days = [
        {
            "number": day,
            "date": date(year, month, day),
            "weekend": date(year, month, day).weekday() >= 5,
        }
        for day in range(1, last.day + 1)
    ]

    rows = []
    for employee in employees:
        cells = []
        for day in days:
            key = (employee.pk, day["number"])
            cells.append({"hours": hours_by_cell.get(key), "leave": leave_by_cell.get(key, ""), "weekend": day["weekend"]})
        total = sum((cell["hours"] or ZERO) for cell in cells)
        rows.append({"employee": employee, "cells": cells, "total": total})

    grand_total = sum((row["total"] for row in rows), ZERO)

    previous = (year - 1, 12) if month == 1 else (year, month - 1)
    following = (year + 1, 1) if month == 12 else (year, month + 1)

    return render(
        request,
        "hr/timesheet.html",
        {
            "page_title": f"Registro presenze {calendar.month_name[month]} {year}",
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "years": [str(number) for number in range(today.year - 3, today.year + 2)],
            "months": [(str(number), calendar.month_name[number]) for number in range(1, 13)],
            "days": days,
            "rows": rows,
            "grand_total": grand_total,
            "previous": previous,
            "following": following,
            "pending_count": LeaveRequest.objects.filter(status=LeaveRequest.STATUS_REQUESTED).count(),
        },
    )


# ---------------------------------------------------------- collaboratori
COLLAB_EDIT_ROLES = (ROLE_ADMIN, ROLE_HR)


def collaborator_for(user):
    """Il collaboratore collegato all'utente, se esiste."""
    return Collaborator.objects.filter(user=user).first()


# ---- area riservata al collaboratore: vede e tocca solo i propri rapportini ----
def collaborator_area(request):
    """Pagina iniziale del collaboratore: i suoi rapportini e i totali."""
    from . import services

    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return render(request, "hr/collaborator_no_link.html", {"page_title": "La mia area"})

    oggi = timezone.localdate()
    entries = (
        collaboratore.time_entries.select_related("job")
        .prefetch_related("expenses")
        .order_by("-date", "-pk")[:60]
    )
    da_rimborsare = services.spese_da_rimborsare().filter(entry__collaborator=collaboratore)
    return render(
        request,
        "hr/collaborator_area.html",
        {
            "page_title": "I miei rapportini",
            "collaborator": collaboratore,
            "entries": entries,
            "hours_month": collaboratore.hours_in_month(oggi.year, oggi.month),
            "hours_total": collaboratore.hours_total(),
            "hours_year": collaboratore.time_entries.filter(date__year=oggi.year).aggregate(
                total=Sum("hours")
            )["total"] or ZERO,
            "to_reimburse": da_rimborsare.aggregate(total=Sum("amount"))["total"] or ZERO,
            "to_fix": collaboratore.time_entries.filter(status=CollaboratorTimeEntry.STATUS_REJECTED).count(),
        },
    )


def _conta_spese(entry, spese):
    """Quante spese avrà il rapportino dopo il salvataggio."""
    if spese is None:
        return entry.expenses.count() if entry.pk else 0
    quante = 0
    for form in spese.forms:
        if form.cleaned_data.get("DELETE"):
            continue
        if form.instance.pk or form.has_changed():
            quante += 1
    return quante


def _modulo_rapportino(request, collaboratore, entry=None):
    """Modulo del rapportino: nuovo oppure da correggere."""
    from . import services

    istanza = entry or CollaboratorTimeEntry(collaborator=collaboratore)
    if request.method == "POST":
        form = RapportinoForm(request.POST, request.FILES, instance=istanza, collaborator=collaboratore)
        # Le spese sono facoltative: un invio senza il blocco delle spese
        # (vecchie pagine rimaste aperte) vale come «nessuna spesa nuova».
        spese = None
        if "spese-TOTAL_FORMS" in request.POST:
            spese = SpeseFormSet(request.POST, request.FILES, instance=istanza, prefix="spese")
        if form.is_valid() and (spese is None or spese.is_valid()):
            if form.cleaned_data["hours"] == 0 and not _conta_spese(istanza, spese):
                form.add_error("hours", "Indica le ore lavorate oppure aggiungi almeno una spesa.")
            else:
                try:
                    salvato = services.salva_rapportino(
                        form.save(commit=False), spese, form.cleaned_data.get("foto") or [], request.user
                    )
                except ValidationError as exc:
                    messages.error(request, "; ".join(exc.messages))
                    return redirect("hr:collaborator_area")
                messages.success(
                    request,
                    f"Rapportino del {salvato.date:%d/%m/%Y} inviato all'ufficio: lo trovi qui sotto in «Da confermare».",
                )
                return redirect("hr:collaborator_area")
        messages.error(request, "Controlla i campi segnalati in rosso.")
    else:
        form = RapportinoForm(
            instance=istanza,
            collaborator=collaboratore,
            initial=None if entry else {"date": timezone.localdate()},
        )
        spese = SpeseFormSet(instance=istanza, prefix="spese")

    if spese is None:
        spese = SpeseFormSet(instance=istanza, prefix="spese")
    return render(
        request,
        "hr/report_form.html",
        {
            "form": form,
            "spese": spese,
            "collaborator": collaboratore,
            "entry": entry,
            "photos": list(entry.attachments.filter(kind=Attachment.KIND_SITE)) if entry else [],
            "page_title": "Correggi il rapportino" if entry else "Nuovo rapportino",
        },
    )


def collaborator_entry_create(request):
    """Il collaboratore compila il rapportino della giornata."""
    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")
    return _modulo_rapportino(request, collaboratore)


def collaborator_entry_update(request, pk):
    """Il collaboratore corregge un proprio rapportino non ancora confermato."""
    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")
    entry = get_object_or_404(CollaboratorTimeEntry, pk=pk, collaborator=collaboratore)
    if not entry.editable_by_collaborator:
        messages.info(request, "Questo rapportino è già stato confermato dall'ufficio: non si può più modificare.")
        return redirect("hr:collaborator_entry_detail", pk=entry.pk)
    return _modulo_rapportino(request, collaboratore, entry)


def collaborator_entry_detail(request, pk):
    """Il collaboratore rilegge un proprio rapportino (con lo stato)."""
    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")
    entry = get_object_or_404(
        CollaboratorTimeEntry.objects.select_related("job", "reviewed_by"), pk=pk, collaborator=collaboratore
    )
    return render(request, "hr/report_detail.html", _contesto_rapportino(entry, ufficio=False))


def collaborator_entry_delete(request, pk):
    """Il collaboratore cancella un proprio rapportino non ancora confermato."""
    from . import services

    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")
    entry = get_object_or_404(CollaboratorTimeEntry, pk=pk, collaborator=collaboratore)
    if request.method == "POST":
        try:
            services.elimina_rapportino(entry)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Rapportino eliminato.")
    return redirect("hr:collaborator_area")


def _contesto_rapportino(entry, ufficio):
    """Dati comuni alla scheda del rapportino (collaboratore e ufficio)."""
    spese = list(entry.expenses.select_related("receipt"))
    allegati = list(entry.attachments.select_related("uploaded_by"))
    ricevute = {spesa.receipt_id for spesa in spese if spesa.receipt_id}
    return {
        "page_title": f"Rapportino del {entry.date:%d/%m/%Y}",
        "entry": entry,
        "collaborator": entry.collaborator,
        "expenses": spese,
        "expenses_total": sum((spesa.amount for spesa in spese), ZERO),
        "to_reimburse_total": sum((spesa.amount for spesa in spese if spesa.to_reimburse), ZERO),
        "photos": [a for a in allegati if a.pk not in ricevute],
        "ufficio": ufficio,
    }


def collaborator_photo_delete(request, pk):
    """Il collaboratore cancella una propria foto."""
    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")
    foto = get_object_or_404(Attachment, pk=pk, collaborator=collaboratore)
    if request.method == "POST":
        descrizione = foto.name
        foto.file.delete(save=False)
        foto.delete()
        messages.success(request, f"Foto «{descrizione}» eliminata.")
    return redirect("hr:collaborator_photos")


def collaborator_photos(request):
    """Foto del cantiere e bolle caricate dal collaboratore."""
    collaboratore = collaborator_for(request.user)
    if collaboratore is None:
        return redirect("hr:collaborator_area")

    if request.method == "POST":
        form = CollaboratorPhotoForm(request.POST, request.FILES, collaborator=collaboratore)
        if form.is_valid():
            foto = Attachment(
                file=form.cleaned_data["file"],
                kind=form.cleaned_data["kind"],
                job=form.cleaned_data["job"],
                notes=form.cleaned_data["notes"],
                collaborator=collaboratore,
                uploaded_by=request.user,
            )
            foto.save()
            dimensione = foto.size_kb
            messages.success(
                request,
                f"Caricata «{foto.name}»" + (f" ({dimensione} KB)." if dimensione else "."),
            )
            return redirect("hr:collaborator_photos")
    else:
        form = CollaboratorPhotoForm(collaborator=collaboratore)

    foto = list(collaboratore.photos.select_related("job", "uploaded_by"))
    return render(
        request,
        "hr/collaborator_photos.html",
        {
            "page_title": "Foto del cantiere",
            "collaborator": collaboratore,
            "form": form,
            "photos": foto,
            "photos_site": [f for f in foto if f.kind == Attachment.KIND_SITE],
            "photos_receipt": [f for f in foto if f.kind == Attachment.KIND_RECEIPT],
        },
    )


# ---- gestione dall'ufficio ----
class CollaboratorListView(RoleRequiredMixin, ListView):
    allowed_roles = COLLAB_EDIT_ROLES
    model = Collaborator
    template_name = "hr/collaborator_list.html"
    context_object_name = "collaborators"
    paginate_by = 25

    def get_queryset(self):
        queryset = Collaborator.objects.select_related("user", "contact").order_by("name")
        stato = self.request.GET.get("stato", "attivi")
        if stato == "attivi":
            queryset = queryset.filter(active=True)
        elif stato == "cessati":
            queryset = queryset.filter(active=False)
        cerca = self.request.GET.get("q", "").strip()
        if cerca:
            queryset = queryset.filter(
                Q(name__icontains=cerca)
                | Q(company__icontains=cerca)
                | Q(specialization__icontains=cerca)
                | Q(code__icontains=cerca)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        oggi = timezone.localdate()
        righe = []
        for collaboratore in context["collaborators"]:
            righe.append(
                {
                    "collaborator": collaboratore,
                    "hours_month": collaboratore.hours_in_month(oggi.year, oggi.month),
                    "hours_total": collaboratore.hours_total(),
                }
            )
        context["rows"] = righe
        context["page_title"] = "Collaboratori"
        context["status"] = self.request.GET.get("stato", "attivi")
        context["search"] = self.request.GET.get("q", "")
        context["active_count"] = Collaborator.objects.filter(active=True).count()
        return context


class CollaboratorCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = COLLAB_EDIT_ROLES
    model = Collaborator
    form_class = CollaboratorForm
    template_name = "hr/collaborator_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:collaborator_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo collaboratore"
        context["cancel_url"] = reverse("hr:collaborator_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Collaboratore «{form.instance.name}» creato.")
        return super().form_valid(form)


class CollaboratorUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
    allowed_roles = COLLAB_EDIT_ROLES
    model = Collaborator
    form_class = CollaboratorForm
    template_name = "hr/collaborator_form.html"

    def get_success_url(self):
        return reverse_lazy("hr:collaborator_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica collaboratore: {self.object.name}"
        context["cancel_url"] = reverse("hr:collaborator_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Collaboratore aggiornato.")
        return super().form_valid(form)


@role_required(*COLLAB_EDIT_ROLES)
def collaborator_delete(request, pk):
    collaboratore = get_object_or_404(Collaborator, pk=pk)
    if request.method == "POST":
        nome = collaboratore.name
        collaboratore.delete()
        messages.success(request, f"Collaboratore «{nome}» eliminato con le sue registrazioni.")
        return redirect("hr:collaborator_list")
    return redirect("hr:collaborator_list")


class CollaboratorTimeListView(RoleRequiredMixin, ListView):
    """Tutte le ore dei collaboratori, per l'ufficio."""

    allowed_roles = COLLAB_EDIT_ROLES
    model = CollaboratorTimeEntry
    template_name = "hr/collaborator_time_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        queryset = CollaboratorTimeEntry.objects.select_related("collaborator", "job", "job__customer")
        collaborator_id = self.request.GET.get("collaboratore", "")
        if collaborator_id:
            queryset = queryset.filter(collaborator_id=collaborator_id)
        job_id = self.request.GET.get("cantiere", "")
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        oggi = timezone.localdate()
        anno = _parse_int(self.request.GET.get("anno"), oggi.year, 2000, 2100)
        mese = self.request.GET.get("mese", "")
        if mese:
            numero = _parse_int(mese, 0, 1, 12)
            if numero:
                queryset = queryset.filter(date__year=anno, date__month=numero)
        return queryset.order_by("-date", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.jobs.models import Job

        oggi = timezone.localdate()
        context["page_title"] = "Ore dei collaboratori"
        context["collaborators"] = Collaborator.objects.order_by("name")
        context["jobs"] = Job.objects.select_related("customer").order_by("name")
        context["collaborator_id"] = self.request.GET.get("collaboratore", "")
        context["job_id"] = self.request.GET.get("cantiere", "")
        context["year"] = _parse_int(self.request.GET.get("anno"), oggi.year, 2000, 2100)
        context["month"] = self.request.GET.get("mese", "")
        context["months"] = [(str(n), calendar.month_name[n]) for n in range(1, 13)]
        context["years"] = [str(n) for n in range(oggi.year - 3, oggi.year + 2)]
        context["filtered_total"] = self.get_queryset().aggregate(total=Sum("hours"))["total"] or ZERO
        return context


@role_required(*COLLAB_EDIT_ROLES)
def collaborator_time_delete(request, pk):
    entry = get_object_or_404(CollaboratorTimeEntry, pk=pk)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Registrazione eliminata.")
    return redirect("hr:collaborator_time_list")


# ---- rapportini: controllo dall'ufficio ----
def _rapportini_con_totali():
    """Rapportini con totale spese e numero di foto, senza moltiplicare le righe."""
    totale_spese = (
        CollaboratorExpense.objects.filter(entry=OuterRef("pk"))
        .values("entry")
        .annotate(totale=Sum("amount"))
        .values("totale")
    )
    numero_foto = (
        Attachment.objects.filter(report=OuterRef("pk"), kind=Attachment.KIND_SITE)
        .values("report")
        .annotate(quante=Count("pk"))
        .values("quante")
    )
    return CollaboratorTimeEntry.objects.select_related("collaborator", "job", "job__customer").annotate(
        totale_spese=Subquery(totale_spese), numero_foto=Subquery(numero_foto)
    )


FILTRI_STATO = {
    "da_confermare": CollaboratorTimeEntry.STATUS_SUBMITTED,
    "confermati": CollaboratorTimeEntry.STATUS_APPROVED,
    "da_correggere": CollaboratorTimeEntry.STATUS_REJECTED,
}


@role_required(*COLLAB_EDIT_ROLES)
def report_list(request):
    """Rapportini dei collaboratori: per prima la coda da confermare."""
    from apps.jobs.models import Job

    stato = request.GET.get("stato", "da_confermare")
    rapportini = _rapportini_con_totali()
    if stato in FILTRI_STATO:
        rapportini = rapportini.filter(status=FILTRI_STATO[stato])
    collaboratore_id = request.GET.get("collaboratore", "")
    if collaboratore_id.isdigit():
        rapportini = rapportini.filter(collaborator_id=int(collaboratore_id))
    cantiere_id = request.GET.get("cantiere", "")
    if cantiere_id.isdigit():
        rapportini = rapportini.filter(job_id=int(cantiere_id))
    # La coda si smaltisce dal più vecchio; gli archivi dal più recente.
    ordine = ("date", "pk") if stato == "da_confermare" else ("-date", "-pk")
    rapportini = rapportini.order_by(*ordine)

    pagina = Paginator(rapportini, 50).get_page(request.GET.get("page"))
    conteggi = CollaboratorTimeEntry.objects.aggregate(
        da_confermare=Count("pk", filter=Q(status=CollaboratorTimeEntry.STATUS_SUBMITTED)),
        da_correggere=Count("pk", filter=Q(status=CollaboratorTimeEntry.STATUS_REJECTED)),
    )
    return render(
        request,
        "hr/report_list.html",
        {
            "page_title": "Rapportini dei collaboratori",
            "page_obj": pagina,
            "entries": pagina.object_list,
            "stato": stato,
            "conteggi": conteggi,
            "collaborators": Collaborator.objects.order_by("name"),
            "jobs": Job.objects.exclude(status__in=[Job.STATUS_CLOSED, Job.STATUS_CANCELLED]).order_by("name"),
            "collaboratore_id": collaboratore_id,
            "cantiere_id": cantiere_id,
        },
    )


@role_required(*COLLAB_EDIT_ROLES)
def report_detail(request, pk):
    """Scheda del rapportino per l'ufficio, con conferma e rimando."""
    entry = get_object_or_404(
        CollaboratorTimeEntry.objects.select_related("collaborator", "job", "job__customer", "reviewed_by", "created_by"),
        pk=pk,
    )
    contesto = _contesto_rapportino(entry, ufficio=True)
    contesto["reject_form"] = RimandaRapportinoForm()
    contesto["in_coda"] = CollaboratorTimeEntry.objects.filter(status=CollaboratorTimeEntry.STATUS_SUBMITTED).count()
    return render(request, "hr/report_detail.html", contesto)


def _prossimo_da_confermare():
    return (
        CollaboratorTimeEntry.objects.filter(status=CollaboratorTimeEntry.STATUS_SUBMITTED)
        .order_by("date", "pk")
        .values_list("pk", flat=True)
        .first()
    )


@role_required(*COLLAB_EDIT_ROLES)
def report_approve(request, pk):
    """Conferma il rapportino e passa al prossimo della coda."""
    from . import services

    entry = get_object_or_404(CollaboratorTimeEntry.objects.select_related("collaborator"), pk=pk)
    if request.method != "POST":
        return redirect("hr:report_detail", pk=entry.pk)
    try:
        services.conferma_rapportino(entry, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("hr:report_detail", pk=entry.pk)
    messages.success(request, f"Rapportino di {entry.collaborator.name} del {entry.date:%d/%m/%Y} confermato.")
    prossimo = _prossimo_da_confermare()
    if prossimo:
        return redirect("hr:report_detail", pk=prossimo)
    return redirect("hr:report_list")


@role_required(*COLLAB_EDIT_ROLES)
def report_reject(request, pk):
    """Rimanda il rapportino al collaboratore con una nota."""
    from . import services

    entry = get_object_or_404(CollaboratorTimeEntry.objects.select_related("collaborator"), pk=pk)
    if request.method != "POST":
        return redirect("hr:report_detail", pk=entry.pk)
    form = RimandaRapportinoForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("Scrivi cosa va corretto: il collaboratore vedrà la nota.")
        services.rimanda_rapportino(entry, request.user, form.cleaned_data["nota"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("hr:report_detail", pk=entry.pk)
    messages.warning(request, f"Rapportino rimandato a {entry.collaborator.name} con la nota.")
    prossimo = _prossimo_da_confermare()
    if prossimo:
        return redirect("hr:report_detail", pk=prossimo)
    return redirect("hr:report_list")


@role_required(*COLLAB_EDIT_ROLES)
def expense_reimbursements(request):
    """Spese pagate dai collaboratori da rimborsare, raggruppate per persona."""
    from . import services

    spese = list(services.spese_da_rimborsare().order_by("entry__collaborator__name", "entry__date", "pk"))
    gruppi = {}
    for spesa in spese:
        collaboratore = spesa.entry.collaborator
        gruppo = gruppi.setdefault(collaboratore.pk, {"collaborator": collaboratore, "expenses": [], "total": ZERO})
        gruppo["expenses"].append(spesa)
        gruppo["total"] += spesa.amount
    rimborsate = (
        CollaboratorExpense.objects.filter(reimbursed_at__isnull=False)
        .select_related("entry__collaborator", "reimbursed_by")
        .order_by("-reimbursed_at", "-pk")[:30]
    )
    return render(
        request,
        "hr/expense_reimbursements.html",
        {
            "page_title": "Rimborsi spese dei collaboratori",
            "groups": list(gruppi.values()),
            "grand_total": sum((gruppo["total"] for gruppo in gruppi.values()), ZERO),
            "reimbursed": rimborsate,
        },
    )


@role_required(*COLLAB_EDIT_ROLES)
def expense_reimburse(request):
    """Segna come rimborsate le spese mostrate in pagina per un collaboratore."""
    from . import services

    if request.method == "POST":
        quante = services.segna_rimborsate(request.POST.getlist("spesa"), request.user)
        if quante == 1:
            messages.success(request, "1 spesa segnata come rimborsata.")
        elif quante:
            messages.success(request, f"{quante} spese segnate come rimborsate.")
        else:
            messages.info(request, "Nessuna spesa da segnare: forse erano già state rimborsate.")
    return redirect("hr:expense_reimbursements")
