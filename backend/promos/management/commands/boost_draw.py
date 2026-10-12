"""
Draw a month's Pays it forward winner, reproducibly.

    python manage.py boost_draw 2026-11 --public "NGX ASI 1 Dec 2026: 98,765.43"

Publish the public value's source before the draw (e.g. "the NGX All-Share index at close on 1 Dec"), then anyone can
recompute the seed: sha256("2026-11|<public value>|<entry ids>"), winner = seed mod pool size.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.services import FlowError
from promos.services import draw


class Command(BaseCommand):
    help = "Draw a month's Pays it forward winner."

    def add_arguments(self, parser):
        parser.add_argument("month", help="YYYY-MM")
        parser.add_argument("--public", required=True, help="The public value announced before the draw.")

    def handle(self, month, public, **opts):
        try:
            m = draw(month, public)
        except FlowError as e:
            raise CommandError(e.message)
        w = m.winner
        self.stdout.write(f"{m.month}: {m.pool_size} entries, seed {m.seed}")
        self.stdout.write(f"Winner: entry {w.pk}, {w.user.first_name.title()} {w.user.last_name[:1]}. for {w.recipient.label if w.recipient else '?'}")
        self.stdout.write("Check it in the admin, fund the Paystack balance with the prize, then run boost_pay.")
