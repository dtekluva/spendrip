"""
Email last month's Google Search Console report.

    python manage.py seo_report                 # last full month, to SEO_REPORT_TO
    python manage.py seo_report --to me@x.com   # somewhere else
    python manage.py seo_report --dry-run       # print the text version, send nothing

Run monthly from the server's cron (on the 4th: Search Console data lags two to three days). See docs/DEPLOY.md.
"""
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notifications.emails import send_raw
from seo import report
from seo.search_console import Client, NotConfigured


class Command(BaseCommand):
    help = "Email last month's Search Console report."

    def add_arguments(self, parser):
        parser.add_argument("--to", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--today", default=None, help="Pretend it's this date (YYYY-MM-DD); the report covers the month before.")

    def handle(self, *args, to=None, dry_run=False, today=None, **opts):
        try:
            client = Client()
        except NotConfigured as e:
            raise CommandError(str(e))
        data = report.fetch(client, date.fromisoformat(today) if today else date.today())
        subject, text, html = report.render(data)
        if dry_run:
            self.stdout.write(text)
            return
        to = to or settings.SEARCH_CONSOLE["REPORT_TO"]
        if not send_raw(to, subject, text, html, fail_silently=False):
            raise CommandError(f"Sending to {to} failed.")
        self.stdout.write(f"Sent to {to}: {subject}")
