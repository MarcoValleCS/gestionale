from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Impostazioni di base"

    def ready(self):
        """Aggancia il registro modifiche ai modelli principali."""
        if not getattr(settings, "ATTIVITA_REGISTRO", True):
            return
        from . import activity

        activity.connetti_pre_save()

        from apps.billing.models import DeliveryNote, PurchaseInvoice, SalesInvoice
        from apps.catalog.models import Product
        from apps.contacts.models import Contact
        from apps.purchasing.models import PurchaseOrder
        from apps.sales.models import Quote, SalesOrder

        activity.sorveglia(
            Quote, SalesOrder, PurchaseOrder, DeliveryNote, SalesInvoice, PurchaseInvoice, Product, Contact
        )
