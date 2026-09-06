from django.core.management.base import BaseCommand

from accounts.registration_services import purge_retained_pending_registrations


class Command(BaseCommand):
    help = "Delete pending registrations after their retention window"

    def handle(self, *args, **options):
        deleted_count = purge_retained_pending_registrations()
        self.stdout.write(f"Deleted {deleted_count} expired pending registration(s)")
