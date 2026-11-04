from django.db import migrations

ADD = {
    "admin": ["task.monitor", "project.control"],
    "pm": ["task.monitor", "project.control"],
}


def add_permissions(apps, schema_editor):
    RoleDefinition = apps.get_model("identity", "RoleDefinition")
    for code, perms in ADD.items():
        for role in RoleDefinition.objects.filter(code=code):
            role.permissions = sorted({*role.permissions, *perms})
            role.save(update_fields=["permissions"])


def remove_permissions(apps, schema_editor):
    RoleDefinition = apps.get_model("identity", "RoleDefinition")
    for code, perms in ADD.items():
        for role in RoleDefinition.objects.filter(code=code):
            role.permissions = [p for p in role.permissions if p not in perms]
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("identity", "0004_role_view_internal_permission")]
    operations = [migrations.RunPython(add_permissions, remove_permissions)]
