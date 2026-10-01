import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from drips.worker import Worker

log = logging.getLogger("spendrip.worker")


class Command(BaseCommand):
    help = "Run the SpenDrip payout worker."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run a single tick and exit.")

    def handle(self, *args, once=False, **opts):
        worker = Worker()
        stop = {"now": False}
        signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
        interval = settings.SPENDRIP["WORKER_TICK_SECONDS"]
        self.stdout.write(f"SpenDrip worker started (provider={worker.provider.name}, every {interval}s)")
        while not stop["now"]:
            close_old_connections()
            try:
                stats = worker.tick()
                if any(stats.get(k) for k in ("handled", "checked")):
                    log.info("tick %s", stats)
            except Exception:
                log.exception("tick failed")
            if once:
                break
            time.sleep(interval)
