import uuid

from django.db import migrations, models


def assign_public_tokens(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    for project in Project.objects.all().only("pk"):
        project.public_token = uuid.uuid4()
        project.save(update_fields=["public_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_boardcolumn_feedbackcard_presentationconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="public_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="is_public",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="project",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(assign_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="project",
            name="public_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
