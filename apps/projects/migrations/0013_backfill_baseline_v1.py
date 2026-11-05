from django.db import migrations


def backfill(apps, schema_editor):
    """Project yang sudah punya kurva baseline mendapat versi 1 yang berlaku."""
    Project = apps.get_model("projects", "Project")
    Baseline = apps.get_model("projects", "Baseline")
    Snapshot = apps.get_model("projects", "ProgressSnapshot")
    Task = apps.get_model("work", "Task")
    for project in Project.objects.all():
        points = list(project.baseline_points.order_by("date"))
        if not points:
            continue
        tasks = [
            {
                "id": t.pk,
                "title": t.title,
                "parent": t.parent_task_id,
                "start": t.baseline_start_date.isoformat() if t.baseline_start_date else None,
                "end": t.baseline_end_date.isoformat() if t.baseline_end_date else None,
                "weight": str(t.weight),
            }
            for t in Task.objects.filter(project=project)
        ]
        baseline = Baseline.objects.create(
            project=project,
            version=1,
            status="active",
            created_by=project.manager,
            note="Dibuat otomatis dari baseline sebelum versioning.",
            baseline_data={
                "tasks": tasks,
                "milestones": [],
                "phases": [],
                "curve": [[p.date.isoformat(), str(p.planned_percent)] for p in points],
            },
        )
        Snapshot.objects.filter(project=project, baseline__isnull=True).update(baseline=baseline)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0012_baseline_versions"),
        ("work", "0010_task_actual_start"),
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
