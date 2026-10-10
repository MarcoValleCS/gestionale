"""Indici per i filtri del registro attività (utente/tipo/azione)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0016_companysettings_sales_terms")]

    operations = [
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["user", "-created_at"], name="activity_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["model_name", "-created_at"], name="activity_type_date_idx"),
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["action", "-created_at"], name="activity_action_date_idx"),
        ),
    ]
