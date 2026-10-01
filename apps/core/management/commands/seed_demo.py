"""Crea dati di esempio per provare il gestionale.

Uso: python manage.py seed_demo
"""
from datetime import timedelta
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

        from apps.sales.models import QuoteTemplate, QuoteTemplateLine

        if not QuoteTemplate.objects.exists():
            bagno = QuoteTemplate.objects.create(
                name="Bagno completo – composizione base",
                description="Mobile, lavabo, specchio e posa in opera",
                payment_term=terms,
                terms_text="Validità offerta 30 giorni.\nPosa inclusa; smaltimento a parte.",
                sort_order=1,
            )
            QuoteTemplateLine.objects.create(
                template=bagno, position=1, description="Mobile bagno 80 cm sospeso", qty=1, uom=pz,
                unit_price=Decimal("450.00"), vat_rate=vat22,
            )
            QuoteTemplateLine.objects.create(
                template=bagno, position=2, description="Specchio con luce LED 80 cm", qty=1, uom=pz,
                unit_price=Decimal("180.00"), vat_rate=vat22,
            )
            QuoteTemplateLine.objects.create(
                template=bagno, position=3, product=montaggio, description="Posa in opera", qty=Decimal("5"), uom=h,
                unit_price=Decimal("45.00"), vat_rate=vat22,
            )

            piscina = QuoteTemplate.objects.create(
                name="Piscina – manutenzione stagionale",
                description="Apertura, chiusura e controlli stagionali",
                payment_term=terms,
                terms_text="Interventi programmati su appuntamento.",
                sort_order=2,
            )
            QuoteTemplateLine.objects.create(
                template=piscina, position=1, description="Apertura piscina (pulizia, avvio impianto, trattamento)", qty=1, uom=pz,
                unit_price=Decimal("350.00"), vat_rate=vat22,
            )
            QuoteTemplateLine.objects.create(
                template=piscina, position=2, description="Chiusura piscina (invernaggio e copertura)", qty=1, uom=pz,
                unit_price=Decimal("320.00"), vat_rate=vat22,
            )
            QuoteTemplateLine.objects.create(
                template=piscina, position=3, product=montaggio, description="Interventi in cantiere", qty=Decimal("4"), uom=h,
                unit_price=Decimal("45.00"), vat_rate=vat22,
            )
            self.stdout.write(self.style.SUCCESS("Creati due modelli di preventivo di esempio (bagno e piscina)."))

        # Cantiere, seriale e manutenzione di esempio
        from datetime import timedelta

        from apps.jobs.models import Asset, Job, MaintenancePlan

        if not Job.objects.exists():
            job = Job.objects.create(
                name="Piscina privata – Via Verdi",
                customer=customer,
                status=Job.STATUS_IN_PROGRESS,
                address="Via Verdi 12",
                zip_code="20100",
                city="Milano",
                province="MI",
                start_date=timezone.localdate(),
                notes="Cantiere di esempio: piscina interrata 8x4.",
            )
            # collega solo i documenti di esempio (per non toccare i tuoi)
            SalesOrder.objects.filter(notes__icontains="esempio", job__isnull=True).update(job=job)
            Quote.objects.filter(reference__icontains="demo", job__isnull=True).update(job=job)

            Asset.objects.create(
                product=bullone,
                serial_number="POMPA-DEMO-001",
                job=job,
                customer=customer,
                installed_on=timezone.localdate(),
                warranty_months=24,
                notes="Seriale di esempio (pompa di ricircolo).",
            )

            piscina_template = QuoteTemplate.objects.filter(name__startswith="Piscina").first()
            MaintenancePlan.objects.create(
                name="Manutenzione stagionale piscina",
                customer=customer,
                job=job,
                template=piscina_template,
                frequency=MaintenancePlan.FREQUENCY_ANNUAL,
                next_date=timezone.localdate() + timedelta(days=20),
                notes="Apertura e controlli stagionali.",
            )
            self.stdout.write(self.style.SUCCESS("Creati cantiere, seriale e manutenzione di esempio (visibili in dashboard)."))

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

        # Personale di esempio: dipendenti, ore registrate e ferie
        self._seed_hr(Job.objects.first())

        self.stdout.write(self.style.SUCCESS("Dati di esempio pronti."))
        self.stdout.write("Suggerimento: apri l'articolo «Bullone M8 zincato» per vedere la scorta minima e poi crea un ordine cliente per provare la generazione automatica dell'ordine fornitore.")

    # ------------------------------------------------------------- personale
    def _seed_hr(self, job):
        """Dipendenti di esempio con ore registrate e una richiesta di ferie."""
        from apps.hr.models import Employee, LeaveRequest, TimeEntry

        if Employee.objects.exists():
            return

        today = timezone.localdate()
        people = [
            ("Luca", "Bianchi", "Idraulico", Decimal("22.50"), Decimal("40")),
            ("Sara", "Rossi", "Impiegata ufficio", Decimal("18.00"), Decimal("40")),
            ("Marco", "Ferrari", "Elettricista", Decimal("21.00"), Decimal("40")),
        ]
        employees = []
        for first_name, last_name, qualification, cost, weekly in people:
            employees.append(
                Employee.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    qualification=qualification,
                    hourly_cost=cost,
                    contract_weekly_hours=weekly,
                    holiday_days_per_year=Decimal("26"),
                    rol_hours_per_year=Decimal("40"),
                    hired_on=today.replace(year=today.year - 2, month=3, day=1),
                )
            )

        # Ore delle ultime due settimane feriali, per due dipendenti sul cantiere
        for employee in employees[:2]:
            for offset in range(14):
                day = today - timedelta(days=offset)
                if day.weekday() >= 5:
                    continue
                TimeEntry.objects.create(
                    employee=employee,
                    date=day,
                    hours=Decimal("8") if offset % 3 else Decimal("7.5"),
                    kind=TimeEntry.KIND_ORDINARY,
                    job=job,
                    description="Installazione e montaggio",
                    billable=True,
                )
            TimeEntry.objects.create(
                employee=employee,
                date=today - timedelta(days=1),
                hours=Decimal("2"),
                kind=TimeEntry.KIND_OVERTIME,
                job=job,
                description="Straordinario per consegna",
            )

        # Una richiesta di ferie da approvare e una già approvata
        LeaveRequest.objects.create(
            employee=employees[1],
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=11),
            reason="Vacanza programmata",
        )
        approved = LeaveRequest.objects.create(
            employee=employees[2],
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=today - timedelta(days=21),
            end_date=today - timedelta(days=18),
            reason="Permesso personale",
        )
        approved.approve(None)
        LeaveRequest.objects.create(
            employee=employees[0],
            kind=LeaveRequest.KIND_ROL,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=2),
            hours=Decimal("3"),
            reason="Visita medica",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Creati {len(employees)} dipendenti con ore registrate e richieste di ferie (sezione Personale)."
            )
        )
