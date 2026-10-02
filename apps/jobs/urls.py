from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    # Cantieri
    path("cantieri/", views.JobListView.as_view(), name="job_list"),
    path("cantieri/nuovo/", views.JobCreateView.as_view(), name="job_create"),
    path("cantieri/<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path("cantieri/<int:pk>/modifica/", views.JobUpdateView.as_view(), name="job_update"),
    # Foto di cantieri e bolle (caricate dai collaboratori)
    path("cantieri/foto/", views.photo_list, name="photo_list"),
    path("cantieri/foto/<int:pk>/elimina/", views.photo_delete, name="photo_delete"),
    # Manutenzioni
    path("manutenzioni/", views.MaintenancePlanListView.as_view(), name="maintenance_list"),
    path("manutenzioni/nuova/", views.MaintenancePlanCreateView.as_view(), name="maintenance_create"),
    path("manutenzioni/<int:pk>/", views.MaintenancePlanUpdateView.as_view(), name="maintenance_update"),
    path("manutenzioni/<int:pk>/eseguita/", views.maintenance_advance, name="maintenance_advance"),
    path("manutenzioni/<int:pk>/preventivo/", views.maintenance_create_quote, name="maintenance_create_quote"),
    path("manutenzioni/<int:pk>/elimina/", views.maintenance_delete, name="maintenance_delete"),
]
