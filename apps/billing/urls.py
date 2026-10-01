from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    # DDT
    path("ddt/", views.DeliveryNoteListView.as_view(), name="deliverynote_list"),
    path("ddt/nuovo/", views.DeliveryNoteCreateView.as_view(), name="deliverynote_create"),
    path("ddt/da-ordine/<int:pk>/", views.deliverynote_create_from_order, name="deliverynote_from_order"),
    path("ddt/<int:pk>/", views.DeliveryNoteDetailView.as_view(), name="deliverynote_detail"),
    path("ddt/<int:pk>/modifica/", views.DeliveryNoteUpdateView.as_view(), name="deliverynote_update"),
    path("ddt/<int:pk>/stampa/", views.DeliveryNotePrintView.as_view(), name="deliverynote_print"),
    path("ddt/<int:pk>/emetti/", views.deliverynote_issue, name="deliverynote_issue"),
    path("ddt/<int:pk>/fattura/", views.deliverynote_invoice, name="deliverynote_invoice"),
    path("ddt/<int:pk>/elimina/", views.deliverynote_delete, name="deliverynote_delete"),
    # Fatture emesse
    path("fatture/emesse/", views.SalesInvoiceListView.as_view(), name="salesinvoice_list"),
    path("fatture/emesse/nuova/", views.SalesInvoiceCreateView.as_view(), name="salesinvoice_create"),
    path("fatture/emesse/da-ordine/<int:pk>/", views.salesinvoice_create_from_order, name="salesinvoice_from_order"),
    path("fatture/emesse/<int:pk>/", views.SalesInvoiceDetailView.as_view(), name="salesinvoice_detail"),
    path("fatture/emesse/<int:pk>/modifica/", views.SalesInvoiceUpdateView.as_view(), name="salesinvoice_update"),
    path("fatture/emesse/<int:pk>/stampa/", views.SalesInvoicePrintView.as_view(), name="salesinvoice_print"),
    path("fatture/emesse/<int:pk>/emetti/", views.salesinvoice_issue, name="salesinvoice_issue"),
    path("fatture/emesse/<int:pk>/inviata/", views.salesinvoice_send, name="salesinvoice_send"),
    path("fatture/emesse/<int:pk>/pagata/", views.salesinvoice_pay, name="salesinvoice_pay"),
    path("fatture/emesse/<int:pk>/elimina/", views.salesinvoice_delete, name="salesinvoice_delete"),
    # Email e fatturazione elettronica
    path("fatture/emesse/<int:pk>/email/", views.salesinvoice_email, name="salesinvoice_email"),
    path("fatture/emesse/<int:pk>/sdi/genera/", views.salesinvoice_sdi_generate, name="salesinvoice_sdi_generate"),
    path("fatture/emesse/<int:pk>/sdi/scarica/", views.salesinvoice_sdi_download, name="salesinvoice_sdi_download"),
    path("fatture/emesse/<int:pk>/sdi/invia/", views.salesinvoice_sdi_send, name="salesinvoice_sdi_send"),
    path("fatture/emesse/<int:pk>/sdi/esito/", views.salesinvoice_sdi_status, name="salesinvoice_sdi_status"),
    # Fatture ricevute
    path("fatture/ricevute/", views.PurchaseInvoiceListView.as_view(), name="purchaseinvoice_list"),
    path("fatture/ricevute/nuova/", views.PurchaseInvoiceCreateView.as_view(), name="purchaseinvoice_create"),
    path("fatture/ricevute/da-ordine-fornitore/<int:pk>/", views.purchaseinvoice_create_from_po, name="purchaseinvoice_from_po"),
    path("fatture/ricevute/<int:pk>/", views.PurchaseInvoiceDetailView.as_view(), name="purchaseinvoice_detail"),
    path("fatture/ricevute/<int:pk>/modifica/", views.PurchaseInvoiceUpdateView.as_view(), name="purchaseinvoice_update"),
    path("fatture/ricevute/<int:pk>/registra/", views.purchaseinvoice_register, name="purchaseinvoice_register"),
    path("fatture/ricevute/<int:pk>/pagata/", views.purchaseinvoice_pay, name="purchaseinvoice_pay"),
    path("fatture/ricevute/<int:pk>/elimina/", views.purchaseinvoice_delete, name="purchaseinvoice_delete"),
]
