from django.core.management.base import BaseCommand

from apps.projects.models import CLOSED_LIFECYCLE, Project
from apps.projects.services import record_snapshot, snapshot_due_projects


class Command(BaseCommand):
    help = "Capture daily progress for all active projects (schedule once per day)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--due",
            action="store_true",
            help=(
                "Only capture today's snapshot for projects that do not have one yet. "
                "Safe to run repeatedly and from multiple workers."
            ),
        )

    def handle(self, *args, **options):
        if options["due"]:
            count = snapshot_due_projects()
            self.stdout.write(self.style.SUCCESS(f"Captured {count} due project snapshots."))
            return
        count = 0
        for project in Project.objects.exclude(lifecycle_status__in=CLOSED_LIFECYCLE):
            record_snapshot(project)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Captured {count} project snapshots."))
