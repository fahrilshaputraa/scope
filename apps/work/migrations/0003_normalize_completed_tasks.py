from django.db import migrations
from django.db.models import F


def normalize_done(apps, schema_editor):
    Task = apps.get_model("work", "Task")
    Task.objects.filter(status="done").update(progress=100)
    Task.objects.filter(status="done", completed_at__isnull=True).update(
        completed_at=F("updated_at")
    )


class Migration(migrations.Migration):
    dependencies = [("work", "0002_task_baseline_end_date_task_baseline_start_date_and_more")]
    operations = [migrations.RunPython(normalize_done, migrations.RunPython.noop)]
