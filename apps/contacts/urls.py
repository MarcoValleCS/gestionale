from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.ContactListView.as_view(), name="list"),
    path("nuovo/", views.ContactCreateView.as_view(), name="create"),
    path("crea-rapida/", views.contact_quick_create, name="quick_create"),
    path("<int:pk>/", views.ContactDetailView.as_view(), name="detail"),
    path("<int:pk>/modifica/", views.ContactUpdateView.as_view(), name="update"),
    path("<int:pk>/attiva-disattiva/", views.contact_toggle_active, name="toggle_active"),
]
