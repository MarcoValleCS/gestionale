"""URL principali del progetto."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.static import serve as media_serve


def protected_media(request, path):
    """Serve i file caricati leggendo MEDIA_ROOT a runtime (non all'avvio)."""
    return media_serve(request, path, document_root=settings.MEDIA_ROOT)


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
    path("", include("apps.billing.urls")),
    path("", include("apps.jobs.urls")),
    path("personale/", include("apps.hr.urls")),
    path("", include("apps.core.urls")),
]

# File caricati (logo, allegati) serviti SOLO agli utenti autenticati
urlpatterns += [
    path("media/<path:path>", login_required(protected_media), name="protected_media"),
]
