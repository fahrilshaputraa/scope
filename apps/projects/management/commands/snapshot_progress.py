from django.core.management.base import BaseCommand

from apps.projects.models import Project, ProjectStatus
from apps.projects.services import record_snapshot


class Command(BaseCommand):
    help = "Capture daily progress for all active projects (schedule once per day)."

    def handle(self, *args, **options):
        count = 0
        for project in Project.objects.exclude(
            status__in=[ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]
        ):
            record_snapshot(project)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Captured {count} project snapshots."))
