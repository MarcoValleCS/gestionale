from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("cerca/", views.global_search, name="search"),
    # Messaggi interni fra utenti
    path("messaggi/", views.messaggi, name="messaggi"),
    path("messaggi/<int:pk>/", views.conversazione, name="conversazione"),
    # Posta in arrivo della casella aziendale
    path("posta/", views.posta, name="posta"),
    path("posta/sincronizza/", views.posta_sincronizza, name="posta_sincronizza"),
    path("posta/<int:pk>/", views.posta_messaggio, name="posta_messaggio"),
    path("posta/<int:pk>/rispondi/", views.posta_rispondi, name="posta_rispondi"),
    path("posta/<int:pk>/allegato/<int:indice>/", views.posta_allegato, name="posta_allegato"),
    path("impostazioni/", views.settings_home, name="settings"),
    path("impostazioni/azienda/", views.CompanyUpdateView.as_view(), name="company_update"),
    path("impostazioni/email/", views.email_settings, name="email_settings"),
    path("impostazioni/attivita/", views.activity_log, name="activity_log"),
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
