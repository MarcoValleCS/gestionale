from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.PhotoListView.as_view(), name="photo_list"),
    path("carica/", views.photo_create, name="photo_create"),
    path("<int:pk>/", views.photo_detail, name="photo_detail"),
    path("<int:pk>/modifica/", views.photo_update, name="photo_update"),
    path("<int:pk>/elimina/", views.photo_delete, name="photo_delete"),
]
