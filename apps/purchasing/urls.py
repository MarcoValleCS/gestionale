from django.urls import path

from . import views

app_name = "purchasing"

urlpatterns = [
    # Listini
    path("listini/", views.PriceListListView.as_view(), name="pricelist_list"),
    path("listini/nuovo/", views.PriceListCreateView.as_view(), name="pricelist_create"),
    path("listini/<int:pk>/", views.PriceListDetailView.as_view(), name="pricelist_detail"),
    path("listini/<int:pk>/modifica/", views.PriceListUpdateView.as_view(), name="pricelist_update"),
    path("listini/<int:pk>/variazione/", views.pricelist_adjust, name="pricelist_adjust"),
    path("listini/<int:pk>/articolo/nuovo/", views.pricelist_item_create, name="pricelist_item_create"),
    path("listini/articolo/<int:pk>/", views.PriceListItemUpdateView.as_view(), name="pricelist_item_update"),
    path("listini/articolo/<int:pk>/elimina/", views.pricelist_item_delete, name="pricelist_item_delete"),
    # Ordini fornitore
    path("ordini/", views.PurchaseOrderListView.as_view(), name="po_list"),
    path("ordini/nuovo/", views.PurchaseOrderCreateView.as_view(), name="po_create"),
    path("ordini/<int:pk>/", views.PurchaseOrderDetailView.as_view(), name="po_detail"),
    path("ordini/<int:pk>/modifica/", views.PurchaseOrderUpdateView.as_view(), name="po_update"),
    path("ordini/<int:pk>/stampa/", views.PurchaseOrderPrintView.as_view(), name="po_print"),
    path("ordini/<int:pk>/invia/", views.po_send, name="po_send"),
    path("ordini/<int:pk>/conferma/", views.po_confirm, name="po_confirm"),
    path("ordini/<int:pk>/ricevi/", views.po_receive, name="po_receive"),
    path("ordini/<int:pk>/annulla/", views.po_cancel, name="po_cancel"),
    path("ordini/<int:pk>/elimina/", views.po_delete, name="po_delete"),
]
