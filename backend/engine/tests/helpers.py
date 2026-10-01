import itertools
from datetime import datetime
from zoneinfo import ZoneInfo

from engine import PlanLike, Schedule, naira

TZ = "Africa/Lagos"
FEE = naira(50)
_order = itertools.count()


def at(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo(TZ))


def plan(pid: str, amount_naira: int, priority: int | None = None, **schedule) -> PlanLike:
    s = {"time_local": "09:00", "tz": TZ, "starts_at": at("2026-01-01T00:00"), **schedule}
    return PlanLike(id=pid, amount_kobo=naira(amount_naira), schedule=Schedule(**s), priority_rank=priority, order=next(_order))
