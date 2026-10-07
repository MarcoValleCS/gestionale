"""Segna «Preventivo mandato» come fase attivata dalla creazione del preventivo."""
from django.db import migrations


def segna_fase(apps, schema_editor):
    LeadStage = apps.get_model("leads", "LeadStage")
    LeadStage.objects.filter(name__iexact="Preventivo mandato").update(on_quote_created=True)


def annulla_fase(apps, schema_editor):
    LeadStage = apps.get_model("leads", "LeadStage")
    LeadStage.objects.filter(name__iexact="Preventivo mandato").update(on_quote_created=False)


class Migration(migrations.Migration):
    dependencies = [("leads", "0003_leadstage_on_quote_created")]

    operations = [migrations.RunPython(segna_fase, annulla_fase)]
