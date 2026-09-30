"""URL principali del progetto."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Gestionale – Amministrazione"
admin.site.site_title = "Gestionale"
admin.site.index_title = "Amministrazione dati"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("contatti/", include("apps.contacts.urls")),
    path("articoli/", include("apps.catalog.urls")),
    path("magazzino/", include("apps.inventory.urls")),
    path("vendite/", include("apps.sales.urls")),
    path("acquisti/", include("apps.purchasing.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
