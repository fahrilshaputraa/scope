"""Permission baru untuk approval, deliverable, dan audit (Fase 5–8)."""

from django.db import migrations

ADD = {
    "admin": [
        "approval.configure",
        "plan.approve",
        "closure.approve",
        "deliverable.manage",
        "deliverable.accept",
        "task.review",
        "audit.view",
    ],
    "pm": ["approval.configure", "deliverable.manage", "task.review"],
    "member": ["task.review"],
    "owner": ["plan.approve", "closure.approve", "deliverable.accept", "task.review"],
    "client": ["deliverable.accept"],
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
    dependencies = [("identity", "0005_task_monitor_project_control_permissions")]
    operations = [migrations.RunPython(add_permissions, remove_permissions)]
