from django.db import migrations, models

# Status lama mencampur siklus hidup dan kondisi; kondisi kini dihitung (health).
FORWARD = {"on_track": "in_progress", "at_risk": "in_progress", "delayed": "in_progress"}


def split_status(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    for old, new in FORWARD.items():
        Project.objects.filter(lifecycle_status=old).update(lifecycle_status=new)


def merge_status(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.filter(lifecycle_status="draft").update(lifecycle_status="planning")
    Project.objects.filter(lifecycle_status="in_progress").update(lifecycle_status="on_track")


class Migration(migrations.Migration):
    dependencies = [("projects", "0010_project_members_through")]

    operations = [
        migrations.RenameField(model_name="project", old_name="status", new_name="lifecycle_status"),
        migrations.RunPython(split_status, merge_status),
        migrations.AlterField(
            model_name="project",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("draft", "Draf"),
                    ("planning", "Perencanaan"),
                    ("in_progress", "Berjalan"),
                    ("on_hold", "Ditahan"),
                    ("completed", "Selesai"),
                    ("cancelled", "Dibatalkan"),
                ],
                default="planning",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="cancellation_reason",
            field=models.TextField(blank=True, help_text="Wajib diisi saat project dibatalkan."),
        ),
    ]
