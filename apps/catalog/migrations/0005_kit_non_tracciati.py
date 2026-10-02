"""I kit non sono pezzi fisici: a magazzino ci vanno i componenti."""
from django.db import migrations


def kit_non_tracciati(apps, schema_editor):
    Prodotto = apps.get_model("catalog", "Product")
    Prodotto.objects.filter(is_kit=True, is_stock_tracked=True).update(is_stock_tracked=False)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_alter_product_code"),
    ]

    operations = [
        migrations.RunPython(kit_non_tracciati, migrations.RunPython.noop),
    ]
