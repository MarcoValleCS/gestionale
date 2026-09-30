from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import StyledPasswordChangeForm, UserCreateForm, UserUpdateForm
from .models import User
from .permissions import ROLE_ADMIN, RoleRequiredMixin


class UserListView(RoleRequiredMixin, ListView):
    allowed_roles = (ROLE_ADMIN,)
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 50
    queryset = User.objects.prefetch_related("groups").order_by("username")


class UserCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = (ROLE_ADMIN,)
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nuovo utente"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Utente «{self.object.username}» creato correttamente.")
        return response


class UserUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = (ROLE_ADMIN,)
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica utente: {self.object}"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Utente «{self.object.username}» aggiornato.")
        return response


class CustomPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        messages.success(self.request, "Password aggiornata correttamente.")
        return super().form_valid(form)
