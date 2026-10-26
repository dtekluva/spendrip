"""Send someone's monthly Finance email now, for checking it:  python manage.py finance_email you@example.com [--to other@example.com]"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from finance.monthly import send_one


class Command(BaseCommand):
    help = "Send a test monthly Finance email for one person (ignores the date and the once-a-month rule)."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Whose report")
        parser.add_argument("--to", default=None, help="Send it here instead")

    def handle(self, email, to=None, **opts):
        u = User.objects.filter(email=email).first()
        if not u:
            raise CommandError(f"No user with email {email}")
        send_one(u, timezone.now(), force=True, to=to)
        self.stdout.write(f"Sent {u.email}'s Finance email to {to or u.email}.")
