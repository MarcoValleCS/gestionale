from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, RoleRequiredMixin, role_required
from apps.core.models import Tag

from .forms import ContactForm
from .models import Contact

EDIT_ROLES = (ROLE_ADMIN, ROLE_SALES, ROLE_PURCHASING)


class ContactListView(ListView):
    model = Contact
    template_name = "contacts/contact_list.html"
    context_object_name = "contacts"
    paginate_by = 25

    def get_queryset(self):
        queryset = Contact.objects.prefetch_related("tags").order_by("name")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(vat_number__icontains=search)
                | Q(city__icontains=search)
                | Q(email__icontains=search)
            )
        kind = self.request.GET.get("tipo", "")
        if kind == "clienti":
            queryset = queryset.filter(is_customer=True)
        elif kind == "fornitori":
            queryset = queryset.filter(is_supplier=True)
        tag_id = self.request.GET.get("tag", "")
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        if self.request.GET.get("inattivi") != "1":
            queryset = queryset.filter(active=True)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Contatti"
        context["tags"] = Tag.objects.all()
        context["search"] = self.request.GET.get("q", "")
        context["kind"] = self.request.GET.get("tipo", "")
        context["selected_tag"] = self.request.GET.get("tag", "")
        context["show_inactive"] = self.request.GET.get("inattivi") == "1"
        return context


class ContactDetailView(DetailView):
    model = Contact
    template_name = "contacts/contact_detail.html"
    context_object_name = "contact"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        context["page_title"] = contact.name
        context["quotes"] = contact.quotes.select_related("customer").order_by("-date", "-id")[:30]
        context["orders"] = contact.sales_orders.select_related("customer").order_by("-date", "-id")[:30]
        context["purchase_orders"] = contact.purchase_orders.select_related("supplier").order_by("-date", "-id")[:30]
        context["price_lists"] = contact.price_lists.order_by("-valid_from")[:20] if contact.is_supplier else []
        return context


class ContactCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = EDIT_ROLES
    model = Contact
    form_class = ContactForm
    template_name = "contacts/contact_form.html"

    def get_success_url(self):
        return reverse_lazy("contacts:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo contatto"
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Contatto «{form.instance.name}» creato.")
        return super().form_valid(form)


class ContactUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = EDIT_ROLES
    model = Contact
    form_class = ContactForm
    template_name = "contacts/contact_form.html"

    def get_success_url(self):
        return reverse_lazy("contacts:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica: {self.object.name}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Contatto aggiornato.")
        return super().form_valid(form)


@role_required(*EDIT_ROLES)
def contact_toggle_active(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.active = not contact.active
    contact.save(update_fields=["active"])
    if contact.active:
        messages.success(request, f"«{contact.name}» riattivato.")
    else:
        messages.warning(request, f"«{contact.name}» disattivato.")
    return redirect("contacts:detail", pk=contact.pk)
