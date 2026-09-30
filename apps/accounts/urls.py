from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(template_name="accounts/login.html", authentication_form=LoginForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/", views.CustomPasswordChangeView.as_view(), name="password_change"),
    path("utenti/", views.UserListView.as_view(), name="user_list"),
    path("utenti/nuovo/", views.UserCreateView.as_view(), name="user_create"),
    path("utenti/<int:pk>/", views.UserUpdateView.as_view(), name="user_update"),
]
