from django.db import migrations

PERMISSION = "project.view_internal"
SKIP = {"client"}


def add_permission(apps, schema_editor):
    RoleDefinition = apps.get_model("identity", "RoleDefinition")
    for role in RoleDefinition.objects.exclude(code__in=SKIP):
        if PERMISSION not in role.permissions:
            role.permissions = sorted({*role.permissions, PERMISSION})
            role.save(update_fields=["permissions"])


def remove_permission(apps, schema_editor):
    RoleDefinition = apps.get_model("identity", "RoleDefinition")
    for role in RoleDefinition.objects.all():
        if PERMISSION in role.permissions:
            role.permissions = [p for p in role.permissions if p != PERMISSION]
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("identity", "0003_remove_userprofile_role")]
    operations = [migrations.RunPython(add_permission, remove_permission)]
