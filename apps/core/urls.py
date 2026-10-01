from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("impostazioni/", views.settings_home, name="settings"),
    path("impostazioni/azienda/", views.CompanyUpdateView.as_view(), name="company_update"),
    path("impostazioni/iva/", views.VatRateListView.as_view(), name="vat_list"),
    path("impostazioni/iva/nuova/", views.VatRateCreateView.as_view(), name="vat_create"),
    path("impostazioni/iva/<int:pk>/", views.VatRateUpdateView.as_view(), name="vat_update"),
    path("impostazioni/unita-misura/", views.UnitOfMeasureListView.as_view(), name="uom_list"),
    path("impostazioni/unita-misura/nuova/", views.UnitOfMeasureCreateView.as_view(), name="uom_create"),
    path("impostazioni/unita-misura/<int:pk>/", views.UnitOfMeasureUpdateView.as_view(), name="uom_update"),
    path("impostazioni/etichette/", views.TagListView.as_view(), name="tag_list"),
    path("impostazioni/etichette/nuova/", views.TagCreateView.as_view(), name="tag_create"),
    path("impostazioni/etichette/<int:pk>/", views.TagUpdateView.as_view(), name="tag_update"),
    path("impostazioni/pagamenti/", views.PaymentTermListView.as_view(), name="paymentterm_list"),
    path("impostazioni/pagamenti/nuova/", views.PaymentTermCreateView.as_view(), name="paymentterm_create"),
    path("impostazioni/pagamenti/<int:pk>/", views.PaymentTermUpdateView.as_view(), name="paymentterm_update"),
    path("impostazioni/numerazioni/", views.sequence_list, name="sequence_list"),
    # Allegati
    path("allegati/carica/", views.attachment_upload, name="attachment_upload"),
    path("allegati/<int:pk>/elimina/", views.attachment_delete, name="attachment_delete"),
    # Webapp (PWA)
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
]
