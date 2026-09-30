from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    # Preventivi
    path("preventivi/", views.QuoteListView.as_view(), name="quote_list"),
    path("preventivi/nuovo/", views.QuoteCreateView.as_view(), name="quote_create"),
    path("preventivi/<int:pk>/", views.QuoteDetailView.as_view(), name="quote_detail"),
    path("preventivi/<int:pk>/modifica/", views.QuoteUpdateView.as_view(), name="quote_update"),
    path("preventivi/<int:pk>/stampa/", views.QuotePrintView.as_view(), name="quote_print"),
    path("preventivi/<int:pk>/invia/", views.quote_send, name="quote_send"),
    path("preventivi/<int:pk>/accetta/", views.quote_accept, name="quote_accept"),
    path("preventivi/<int:pk>/rifiuta/", views.quote_reject, name="quote_reject"),
    path("preventivi/<int:pk>/converti/", views.quote_convert, name="quote_convert"),
    path("preventivi/<int:pk>/duplica/", views.quote_duplicate, name="quote_duplicate"),
    path("preventivi/<int:pk>/elimina/", views.quote_delete, name="quote_delete"),
    # Ordini cliente
    path("ordini/", views.SalesOrderListView.as_view(), name="order_list"),
    path("ordini/nuovo/", views.SalesOrderCreateView.as_view(), name="order_create"),
    path("ordini/<int:pk>/", views.SalesOrderDetailView.as_view(), name="order_detail"),
    path("ordini/<int:pk>/modifica/", views.SalesOrderUpdateView.as_view(), name="order_update"),
    path("ordini/<int:pk>/stampa/", views.SalesOrderPrintView.as_view(), name="order_print"),
    path("ordini/<int:pk>/conferma/", views.order_confirm, name="order_confirm"),
    path("ordini/<int:pk>/consegna/", views.order_deliver, name="order_deliver"),
    path("ordini/<int:pk>/annulla/", views.order_cancel, name="order_cancel"),
    path("ordini/<int:pk>/elimina/", views.order_delete, name="order_delete"),
]
