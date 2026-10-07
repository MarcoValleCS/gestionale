"""Fasi predefinite della pipeline lead."""
from django.db import migrations

FASI = [
    ("Contatto arrivato", 10, "primary", "open"),
    ("Contattato", 20, "info", "open"),
    ("Preventivo mandato", 30, "warning", "open"),
    ("Sopralluogo effettuato", 40, "dark", "open"),
    ("Contratto chiuso", 50, "success", "won"),
    ("Perso", 60, "danger", "lost"),
]


def crea_fasi(apps, schema_editor):
    LeadStage = apps.get_model("leads", "LeadStage")
    for nome, ordine, colore, esito in FASI:
        LeadStage.objects.get_or_create(
            name=nome, defaults={"order": ordine, "color": colore, "kind": esito}
        )


def rimuovi_fasi(apps, schema_editor):
    LeadStage = apps.get_model("leads", "LeadStage")
    LeadStage.objects.filter(name__in=[nome for nome, *_ in FASI]).delete()


class Migration(migrations.Migration):
    dependencies = [("leads", "0001_initial")]

    operations = [migrations.RunPython(crea_fasi, rimuovi_fasi)]
