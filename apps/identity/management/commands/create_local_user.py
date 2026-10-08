from getpass import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from apps.identity.models import Role


class Command(BaseCommand):
    help = "Create a local account; asks for password without echoing it."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--role", choices=Role.values, default=Role.PROJECT_MANAGER)
        parser.add_argument("--staff", action="store_true")

    def handle(self, *args, **options):
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError("User sudah ada. Gunakan changepassword untuk mengatur password.")
        password = getpass("Password: ")
        if len(password) < 8 or password != getpass("Ulangi password: "):
            raise CommandError("Password minimal 8 karakter dan konfirmasi harus sama.")
        user = User.objects.create_user(
            options["username"], password=password, is_staff=options["staff"]
        )
        user.pcc_profile.role = options["role"]
        user.pcc_profile.save()
        self.stdout.write(self.style.SUCCESS(f"Akun lokal {user.username} dibuat."))
