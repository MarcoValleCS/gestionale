from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    # Cantieri
    path("cantieri/", views.JobListView.as_view(), name="job_list"),
    path("cantieri/nuovo/", views.JobCreateView.as_view(), name="job_create"),
    path("cantieri/<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path("cantieri/<int:pk>/modifica/", views.JobUpdateView.as_view(), name="job_update"),
    # Manutenzioni
    path("manutenzioni/", views.MaintenancePlanListView.as_view(), name="maintenance_list"),
    path("manutenzioni/nuova/", views.MaintenancePlanCreateView.as_view(), name="maintenance_create"),
    path("manutenzioni/<int:pk>/", views.MaintenancePlanUpdateView.as_view(), name="maintenance_update"),
    path("manutenzioni/<int:pk>/eseguita/", views.maintenance_advance, name="maintenance_advance"),
    path("manutenzioni/<int:pk>/preventivo/", views.maintenance_create_quote, name="maintenance_create_quote"),
    path("manutenzioni/<int:pk>/elimina/", views.maintenance_delete, name="maintenance_delete"),
    # Seriali
    path("seriali/", views.AssetListView.as_view(), name="asset_list"),
    path("seriali/nuovo/", views.AssetCreateView.as_view(), name="asset_create"),
    path("seriali/<int:pk>/", views.AssetUpdateView.as_view(), name="asset_update"),
    path("seriali/<int:pk>/elimina/", views.asset_delete, name="asset_delete"),
]
