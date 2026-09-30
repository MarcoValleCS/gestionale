"""Crea dati di esempio per provare il gestionale.

Uso: python manage.py seed_demo
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.contacts.models import Contact
from apps.core.models import PaymentTerm, Tag, UnitOfMeasure, VatRate
from apps.inventory.models import StockMovement
from apps.inventory.services import register_movement
from apps.purchasing.models import PriceListItem, SupplierPriceList
from apps.sales import services as sales_services
from apps.sales.models import Quote, QuoteLine, SalesOrder, SalesOrderLine


class Command(BaseCommand):
    help = "Crea clienti, fornitori, articoli, listino e un preventivo di esempio."

    @transaction.atomic
    def handle(self, *args, **options):
        vat22 = VatRate.objects.filter(code="22").first()
        vat10 = VatRate.objects.filter(code="10").first()
        pz = UnitOfMeasure.objects.get(code="PZ")
        h = UnitOfMeasure.objects.get(code="H")
        terms = PaymentTerm.objects.filter(name="Bonifico 30 giorni").first()

        tag_vip, _ = Tag.objects.get_or_create(name="VIP", defaults={"color": "primary", "description": "Cliente o fornitore prioritario"})
        tag_nuovo, _ = Tag.objects.get_or_create(name="Nuovo", defaults={"color": "info"})
        tag_promo, _ = Tag.objects.get_or_create(name="Promozione", defaults={"color": "warning"})

        categoria, _ = Category.objects.get_or_create(name="Ricambi")

        customer, created = Contact.objects.get_or_create(
            name="Rossi Costruzioni S.r.l.",
            defaults={
                "is_customer": True,
                "is_supplier": False,
                "vat_number": "01234567890",
                "email": "info@rossicostruzioni.example",
                "phone": "02 1234567",
                "address": "Via Roma 10",
                "zip_code": "20100",
                "city": "Milano",
                "province": "MI",
                "payment_term": terms,
            },
        )
        customer.tags.add(tag_vip, tag_nuovo)

        supplier, _ = Contact.objects.get_or_create(
            name="Ferramenta Bianchi S.p.A.",
            defaults={
                "is_customer": False,
                "is_supplier": True,
                "vat_number": "09876543210",
                "email": "ordini@ferramentabianchi.example",
                "phone": "011 7654321",
                "address": "Corso Francia 55",
                "zip_code": "10100",
                "city": "Torino",
                "province": "TO",
                "payment_term": terms,
            },
        )

        bullone, _ = Product.objects.get_or_create(
            name="Bullone M8 zincato",
            defaults={
                "category": categoria,
                "uom": pz,
                "sale_price": Decimal("0.35"),
                "sale_vat": vat22,
                "purchase_price": Decimal("0.18"),
                "purchase_vat": vat22,
                "main_supplier": supplier,
                "min_stock": Decimal("500"),
            },
        )
        bullone.tags.add(tag_promo)

        tondino, _ = Product.objects.get_or_create(
            name="Tondino ferro 8 mm",
            defaults={
                "category": categoria,
                "uom": UnitOfMeasure.objects.get(code="KG"),
                "sale_price": Decimal("1.20"),
                "sale_vat": vat22,
                "purchase_price": Decimal("0.70"),
                "purchase_vat": vat22,
                "main_supplier": supplier,
                "min_stock": Decimal("100"),
            },
        )

        montaggio, _ = Product.objects.get_or_create(
            name="Montaggio in cantiere",
            defaults={
                "uom": h,
                "sale_price": Decimal("45.00"),
                "sale_vat": vat22,
                "purchase_price": Decimal("0"),
                "purchase_vat": vat22,
                "is_stock_tracked": False,
            },
        )

        pricelist, pl_created = SupplierPriceList.objects.get_or_create(
            supplier=supplier,
            name=f"Listino {timezone.localdate().year}",
            defaults={"notes": "Listino di esempio generato da seed_demo."},
        )
        if pl_created:
            PriceListItem.objects.get_or_create(pricelist=pricelist, product=bullone, defaults={"price": Decimal("0.18")})
            PriceListItem.objects.get_or_create(pricelist=pricelist, product=tondino, defaults={"price": Decimal("0.70")})

        if not Quote.objects.exists():
            quote = Quote.objects.create(
                customer=customer,
                payment_term=terms,
                reference="Rif. demo",
                status=Quote.STATUS_DRAFT,
            )
            QuoteLine.objects.create(
                quote=quote, position=1, product=bullone, description=bullone.name,
                qty=Decimal("500"), uom=pz, unit_price=Decimal("0.35"), vat_rate=vat22,
            )
            QuoteLine.objects.create(
                quote=quote, position=2, product=montaggio, description=montaggio.name,
                qty=Decimal("8"), uom=h, unit_price=Decimal("45.00"), vat_rate=vat22,
            )
            quote.recalculate()
            self.stdout.write(self.style.SUCCESS(f"Creato preventivo di esempio {quote.number}."))

        # Ordine consegnato di esempio: alimenta fatturato e marginalità in dashboard
        if not SalesOrder.objects.filter(status=SalesOrder.STATUS_DELIVERED).exists():
            order = SalesOrder.objects.create(
                customer=customer,
                payment_term=terms,
                notes="Ordine di esempio già consegnato.",
            )
            SalesOrderLine.objects.create(
                order=order, position=1, product=bullone, description=bullone.name,
                qty=Decimal("120"), uom=pz, unit_price=Decimal("0.35"), vat_rate=vat22,
            )
            SalesOrderLine.objects.create(
                order=order, position=2, product=montaggio, description=montaggio.name,
                qty=Decimal("6"), uom=h, unit_price=Decimal("45.00"), vat_rate=vat22,
            )
            order.recalculate()
            register_movement(
                product=bullone,
                delta=Decimal("120"),
                movement_type=StockMovement.TYPE_LOAD,
                note="Carico iniziale di esempio",
            )
            sales_services.confirm_sales_order(order)
            sales_services.deliver_sales_order(order)
            self.stdout.write(self.style.SUCCESS(f"Creato ordine consegnato di esempio {order.number} (visibile in dashboard)."))

        self.stdout.write(self.style.SUCCESS("Dati di esempio pronti."))
        self.stdout.write("Suggerimento: apri l'articolo «Bullone M8 zincato» per vedere la scorta minima e poi crea un ordine cliente per provare la generazione automatica dell'ordine fornitore.")
