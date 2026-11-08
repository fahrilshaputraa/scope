from django.core.management.base import BaseCommand

from apps.integrations.events import collect_scheduled_events
from apps.integrations.teams import deliver_pending


class Command(BaseCommand):
    help = (
        "Queue time-based Teams events (overdue, milestones, health, daily summary) and "
        "send queued Teams messages. Safe to re-run: dedupe keys prevent duplicates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-only",
            action="store_true",
            help="Only send the existing queue; skip event detection.",
        )

    def handle(self, *args, **options):
        queued = 0 if options["send_only"] else collect_scheduled_events()
        counts = deliver_pending()
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued {queued}, sent {counts['sent']}, retry {counts['retry']}, "
                f"failed {counts['failed']}, skipped {counts['skipped']} Teams message(s)."
            )
        )
