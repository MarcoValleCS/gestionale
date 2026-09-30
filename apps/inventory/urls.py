from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.StockListView.as_view(), name="stock_list"),
    path("movimenti/", views.MovementListView.as_view(), name="movement_list"),
    path("rettifica/", views.adjust_create, name="adjust_create"),
    path("articolo/<int:pk>/giacenza/", views.stock_info, name="stock_info"),
]
