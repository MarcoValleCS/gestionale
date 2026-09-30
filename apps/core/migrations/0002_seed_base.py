"""Dati iniziali: unità di misura, aliquote IVA, pagamenti, numerazioni, azienda."""
import datetime

from django.db import migrations

UNITS = [
    ("PZ", "Pezzi"),
    ("CF", "Confezione"),
    ("BOX", "Cartone / Box"),
    ("PLT", "Pallet"),
    ("NR", "Numero"),
    ("KG", "Chilogrammi"),
    ("GR", "Grammi"),
    ("MT", "Metri"),
    ("MQ", "Metri quadri"),
    ("MC", "Metri cubi"),
    ("LT", "Litri"),
    ("H", "Ore"),
    ("GG", "Giorni"),
]

VAT_RATES = [
    # codice, nome, aliquota, natura, predef. vendite, predef. acquisti
    ("22", "IVA 22% (aliquota ordinaria)", "22.00", "", True, True),
    ("10", "IVA 10% (aliquota ridotta)", "10.00", "", False, False),
    ("5", "IVA 5% (aliquota ridotta)", "5.00", "", False, False),
    ("4", "IVA 4% (aliquota minima)", "4.00", "", False, False),
    ("0", "Esente art. 10 / aliquota zero", "0.00", "N1", False, False),
    ("N2.2", "Non soggette IVA – altri casi (es. reverse charge interno)", "0.00", "N2.2", False, False),
    ("N3.2", "Non imponibili – esportazioni", "0.00", "N3.2", False, False),
    ("N4", "Split payment – esigibilità IVA", "0.00", "N4", False, False),
    ("N6", "Reverse charge (autofattura)", "0.00", "N6", False, False),
]

PAYMENT_TERMS = [
    ("Rimessa diretta", 0, False),
    ("Bonifico 30 giorni", 30, False),
    ("Bonifico 60 giorni", 60, False),
    ("Bonifico 30/60 giorni", 60, False),
    ("Bonifico 30 gg fine mese", 30, True),
    ("Bonifico 60 gg fine mese", 60, True),
    ("Bonifico 90 gg data fattura", 90, False),
]

DOC_TYPES = ["quote", "sales_order", "purchase_order"]


def seed(apps, schema_editor):
    UnitOfMeasure = apps.get_model("core", "UnitOfMeasure")
    VatRate = apps.get_model("core", "VatRate")
    PaymentTerm = apps.get_model("core", "PaymentTerm")
    NumberSequence = apps.get_model("core", "NumberSequence")
    CompanySettings = apps.get_model("core", "CompanySettings")

    for code, name in UNITS:
        UnitOfMeasure.objects.get_or_create(code=code, defaults={"name": name})

    for code, name, rate, nature, default_sales, default_purchase in VAT_RATES:
        VatRate.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "rate": rate,
                "nature": nature,
                "is_default_sales": default_sales,
                "is_default_purchase": default_purchase,
            },
        )

    for name, days, end_of_month in PAYMENT_TERMS:
        PaymentTerm.objects.get_or_create(name=name, defaults={"days": days, "end_of_month": end_of_month})

    defaults = {
        "quote": "PRE-",
        "sales_order": "OC-",
        "purchase_order": "OF-",
    }
    year = datetime.date.today().year
    for doc_type in DOC_TYPES:
        NumberSequence.objects.get_or_create(
            doc_type=doc_type,
            year=year,
            defaults={"prefix": defaults[doc_type]},
        )

    CompanySettings.objects.get_or_create(pk=1, defaults={"name": "La mia azienda"})


def unseed(apps, schema_editor):
    UnitOfMeasure = apps.get_model("core", "UnitOfMeasure")
    VatRate = apps.get_model("core", "VatRate")
    PaymentTerm = apps.get_model("core", "PaymentTerm")
    UnitOfMeasure.objects.filter(code__in=[c for c, _ in UNITS]).delete()
    VatRate.objects.filter(code__in=[c for c, *_ in VAT_RATES]).delete()
    PaymentTerm.objects.filter(name__in=[n for n, *_ in PAYMENT_TERMS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
