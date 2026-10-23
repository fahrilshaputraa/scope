from django.core.management.base import BaseCommand

from apps.notifications.delivery import deliver_digest
from apps.notifications.models import DigestFrequency


class Command(BaseCommand):
    help = "Send one notification digest per user for the requested frequency."

    def add_arguments(self, parser):
        parser.add_argument(
            "--frequency",
            required=True,
            choices=[DigestFrequency.DAILY, DigestFrequency.WEEKLY],
            help="Digest window: daily or weekly.",
        )

    def handle(self, *args, **options):
        frequency = options["frequency"]
        count = deliver_digest(frequency)
        self.stdout.write(
            self.style.SUCCESS(f"Sent {count} {frequency} notification digest(s).")
        )
