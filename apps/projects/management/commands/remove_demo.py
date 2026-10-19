"""Remove the demo projects created by seed_demo."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.demo import DEMO_PROJECT_CODES
from apps.projects.models import Project
from apps.work.models import Task


class Command(BaseCommand):
    help = "Hapus project demo dari seed_demo. Akun pengguna tidak dihapus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tampilkan project yang akan dihapus tanpa menghapus data.",
        )

    def handle(self, *args, **options):
        projects = Project.objects.filter(code__in=DEMO_PROJECT_CODES).order_by("code")
        count = projects.count()
        if not count:
            self.stdout.write("Tidak ada data demo.")
            return
        if options["dry_run"]:
            for project in projects:
                self.stdout.write(f"- {project.code} — {project.name}")
            self.stdout.write(f"Dry run: {count} project demo akan dihapus.")
            return
        task_count = Task.objects.filter(project__in=projects).count()
        with transaction.atomic():
            projects.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Data demo dihapus: {count} project, {task_count} task. "
                "Akun pengguna demo tetap ada."
            )
        )
