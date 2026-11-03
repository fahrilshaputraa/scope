from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_workspace_roles_memberships"),
    ]

    operations = [
        migrations.RemoveField(model_name="userprofile", name="role"),
    ]
