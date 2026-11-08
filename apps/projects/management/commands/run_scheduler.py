import time

from django.core.management.base import BaseCommand

from apps.projects.scheduler import tick


class Command(BaseCommand):
    help = (
        "Proses terjadwal berkelanjutan untuk container: snapshot progress yang jatuh tempo "
        "serta email notifikasi dan digest. Idempoten, aman dijalankan berdampingan."
    )

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=300, help="Detik antar tick.")
        parser.add_argument("--once", action="store_true", help="Jalankan satu tick lalu keluar.")

    def handle(self, *args, **options):
        interval = max(options["interval"], 1.0)
        while True:
            try:
                count = tick()
                self.stdout.write(f"Tick selesai: {count} snapshot.")
            except Exception as exc:  # satu tick gagal tidak boleh mematikan proses
                self.stderr.write(f"Tick gagal: {exc}")
                if options["once"]:
                    raise
            if options["once"]:
                return
            time.sleep(interval)
