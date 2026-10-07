from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("", views.board, name="board"),
    path("nuovo/", views.LeadCreateView.as_view(), name="lead_create"),
    path("fasi/", views.StageListView.as_view(), name="stage_list"),
    path("fasi/nuova/", views.StageCreateView.as_view(), name="stage_create"),
    path("fasi/<int:pk>/", views.StageUpdateView.as_view(), name="stage_update"),
    path("<int:pk>/", views.LeadDetailView.as_view(), name="lead_detail"),
    path("<int:pk>/modifica/", views.LeadUpdateView.as_view(), name="lead_update"),
    path("<int:pk>/fase/", views.lead_stage, name="lead_stage"),
    path("<int:pk>/elimina/", views.lead_delete, name="lead_delete"),
]
