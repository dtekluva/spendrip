"""Credit the drawn winner's prize to their balance and tell them:  python manage.py boost_pay 2026-11"""
from django.core.management.base import BaseCommand, CommandError

from accounts.services import FlowError
from promos.services import pay


class Command(BaseCommand):
    help = "Pay a drawn Pays it forward winner."

    def add_arguments(self, parser):
        parser.add_argument("month", help="YYYY-MM")

    def handle(self, month, **opts):
        try:
            m = pay(month)
        except FlowError as e:
            raise CommandError(e.message)
        self.stdout.write(f"{m.month}: paid ₦{m.prize_kobo / 100:,.0f} to {m.winner.user.email} (inflow {m.inflow_id}).")
