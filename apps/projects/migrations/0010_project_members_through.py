import django.db.models.deletion  # noqa: F401
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Ganti M2M ``members`` menjadi through ``ProjectMembership`` (data sudah disalin di 0009)."""

    dependencies = [
        ("projects", "0009_owner_workspace_project_membership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(model_name="project", name="members"),
        migrations.AddField(
            model_name="project",
            name="members",
            field=models.ManyToManyField(
                blank=True,
                related_name="member_projects",
                through="projects.ProjectMembership",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
