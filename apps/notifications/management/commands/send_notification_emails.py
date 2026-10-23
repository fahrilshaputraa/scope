from django.core.management.base import BaseCommand

from apps.notifications.delivery import deliver_pending_emails


class Command(BaseCommand):
    help = "Send queued notification emails and mark them as sent (safe to re-run)."

    def handle(self, *args, **options):
        count = deliver_pending_emails()
        self.stdout.write(self.style.SUCCESS(f"Sent {count} notification email(s)."))
