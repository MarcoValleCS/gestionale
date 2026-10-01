"""Aggiunge il ruolo «Collaboratore» (accesso alla sola area ore)."""
from django.db import migrations

NEW_ROLE = "Collaboratore"


def create_role(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=NEW_ROLE)


def remove_role(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=NEW_ROLE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_personale_group"),
    ]

    operations = [
        migrations.RunPython(create_role, remove_role),
    ]
