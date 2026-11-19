from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from .forms import CasellaPersonaleForm, StyledPasswordChangeForm, UserCreateForm, UserUpdateForm
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

    def get_queryset(self):
        # Il ruolo «Amministratore» non è un superutente: non deve poter
        # cambiare la password di un superutente e prenderne il posto.
        utenti = super().get_queryset()
        if not self.request.user.is_superuser:
            utenti = utenti.filter(is_superuser=False)
        return utenti

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifica utente: {self.object}"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Utente «{self.object.username}» aggiornato.")
        return response


class CustomPasswordChangeView(PasswordChangeView):
    """Pagina «Password ed email»: cambio password e casella email personale."""

    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("core:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("casella_form", CasellaPersonaleForm(instance=self.request.user))
        return context

    def form_valid(self, form):
        messages.success(self.request, "Password aggiornata correttamente.")
        return super().form_valid(form)


@require_POST
def casella_email(request):
    """Salva la casella email personale (ed eventualmente manda una prova).

    Con la password della propria casella, preventivi, ordini e fatture
    inviati da questo utente partono dal suo indirizzo (es. simone@aquaforma.it).
    """
    from apps.core.mailing import invia_subito

    form = CasellaPersonaleForm(request.POST, instance=request.user)
    if not form.is_valid():
        contesto = {"form": StyledPasswordChangeForm(user=request.user), "casella_form": form}
        return render(request, "accounts/password_change.html", contesto)
    utente = form.save()
    if not utente.ha_casella_personale:
        messages.success(request, "Email salvata: le tue email partono dalla casella aziendale, con risposte a te.")
    elif request.POST.get("azione") == "prova":
        try:
            invia_subito(
                to_email=utente.email,
                subject="Prova di invio dalla tua casella",
                message="Questa email è partita dal gestionale con la tua casella: l'invio personale funziona.",
                utente=utente,
                solo_personale=True,
            )
        except Exception as exc:
            messages.error(request, f"Casella salvata, ma la prova di invio non è riuscita: {exc}")
        else:
            messages.success(request, f"Casella salvata: email di prova inviata a {utente.email}.")
    else:
        messages.success(request, f"Casella salvata: le tue email partiranno da {utente.email}.")
    return redirect("accounts:password_change")
