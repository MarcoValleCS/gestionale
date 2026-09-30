"""Crea il magazzino principale predefinito."""
from django.db import migrations


def create_warehouse(apps, schema_editor):
    Warehouse = apps.get_model("inventory", "Warehouse")
    Warehouse.objects.get_or_create(
        code="MAG",
        defaults={"name": "Magazzino principale", "is_default": True},
    )


def remove_warehouse(apps, schema_editor):
    Warehouse = apps.get_model("inventory", "Warehouse")
    Warehouse.objects.filter(code="MAG").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_warehouse, remove_warehouse),
    ]
