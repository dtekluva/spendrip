from django.conf import settings
from django.core.management.base import BaseCommand

from notifications.emails import send


class Command(BaseCommand):
    help = "Send a test email to check the mail setup: manage.py send_test_email you@example.com"

    def add_arguments(self, parser):
        parser.add_argument("to")

    def handle(self, to, **opts):
        self.stdout.write(f"Backend: {settings.EMAIL_BACKEND}  From: {settings.DEFAULT_FROM_EMAIL}")
        send(to, "SpenDrip test email", "Email is working 🎉",
             ["This is a test from SpenDrip. If you can read it, sending through Mailgun works."], fail_silently=False)
        self.stdout.write(self.style.SUCCESS(f"Sent to {to}"))
