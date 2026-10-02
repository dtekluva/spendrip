from django.conf import settings
from django.core.management.base import BaseCommand

from notifications.emails import render_delivered, sample_delivered, send, send_raw


class Command(BaseCommand):
    help = "Send a test email: manage.py send_test_email you@example.com [--delivered] [--name Ada] [--save preview.html]"

    def add_arguments(self, parser):
        parser.add_argument("to")
        parser.add_argument("--delivered", action="store_true", help="send a sample 'drip delivered' email")
        parser.add_argument("--name", default="Ada")
        parser.add_argument("--save", help="also write the HTML to this file")

    def handle(self, to, delivered=False, name="Ada", save=None, **opts):
        self.stdout.write(f"Backend: {settings.EMAIL_BACKEND}  From: {settings.DEFAULT_FROM_EMAIL}")
        if delivered:
            subject, text, html = render_delivered(sample_delivered(name))
            if save:
                open(save, "w").write(html)
            send_raw(to, f"[Test] {subject}", text, html, fail_silently=False)
        else:
            send(to, "SpenDrip test email", "Email is working 🎉",
                 ["This is a test from SpenDrip. If you can read it, sending through Mailgun works."], fail_silently=False)
        self.stdout.write(self.style.SUCCESS(f"Sent to {to}"))
