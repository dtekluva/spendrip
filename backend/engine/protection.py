"""
The protection engine.

- Plans share one balance.
- Up to 3 plans can be priorities, ranked 1–3.
- The protected amount is the cost (amount + fee) of every priority run still due between
  now and the end of the current calendar month. So it is prorated to what is left of the
  month and resets on the 1st.
- Priority k may only spend money that leaves enough for the remaining runs of priorities
  1…k-1. A non-priority run may only spend money that leaves enough for ALL remaining
  priority runs.
- An optional daily cap holds back any run that would push one day's sending over it.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from .fees import fee_for
from .schedule import Schedule, day_key, end_of_month, occurrences

# Event statuses
PROTECTED = "protected"  # priority run that will go out
SEND = "send"  # non-priority run that will go out
WAIT = "wait"  # non-priority run held back to protect priorities
SHORT = "short"  # priority run that can't be covered
CAP = "cap"  # held back by the daily cap
GOES_OUT = (PROTECTED, SEND)


@dataclass(frozen=True)
class PlanLike:
    id: str
    amount_kobo: int
    schedule: Schedule
    priority_rank: int | None = None  # 1, 2, 3 or None
    status: str = "active"
    order: int = 0  # tie-break for runs at the same moment and rank (creation order)


@dataclass(frozen=True)
class ForecastEvent:
    plan_id: str
    at: datetime
    amount_kobo: int
    fee_kobo: int
    rank: int | None
    order: int
    status: str = ""

    @property
    def cost_kobo(self) -> int:
        return self.amount_kobo + self.fee_kobo


@dataclass
class Forecast:
    window_end: datetime
    events: list[ForecastEvent]
    protected_kobo: int  # what the priorities need for the rest of the month
    free_kobo: int  # available − protected (can be negative)
    total_needed_kobo: int
    top_up_kobo: int  # top-up that would let every run this month go out
    priority_shortfall_kobo: int  # top-up that would cover just the priorities
    waiting: list[ForecastEvent] = field(default_factory=list)
    short: list[ForecastEvent] = field(default_factory=list)
    capped: list[ForecastEvent] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    ok: bool
    reserved_for_others_kobo: int
    reason: str | None = None  # protected_for_priorities | insufficient_funds | daily_cap
    short_by_kobo: int = 0


def compare_key(at: datetime, rank: int | None, order: int):
    """Sort key: time, then priority (1 first, non-priority last), then creation order."""
    return (at, rank if rank else 99, order)


def validate_priorities(plans) -> list[str]:
    errors, seen = [], {}
    for p in plans:
        if p.priority_rank is None:
            continue
        if p.priority_rank not in (1, 2, 3):
            errors.append(f"plan {p.id}: priority must be 1, 2 or 3")
        if p.priority_rank in seen:
            errors.append(f"plans {seen[p.priority_rank]} and {p.id} both have priority {p.priority_rank}")
        seen[p.priority_rank] = p.id
    return errors


def _events(plans, start: datetime, end: datetime, fee_kobo) -> list[ForecastEvent]:
    events = [
        ForecastEvent(p.id, at, p.amount_kobo, fee_for(fee_kobo, p.amount_kobo), p.priority_rank, p.order)
        for p in plans
        if p.status == "active"
        for at in occurrences(p.schedule, start, end)
    ]
    events.sort(key=lambda e: compare_key(e.at, e.rank, e.order))
    return events


def forecast(plans, available_kobo: int, now: datetime, *, fee_kobo, tz: str,
             daily_cap_kobo: int | None = None, sent_today_kobo: int = 0) -> Forecast:
    """Simulate the rest of the month run by run."""
    window_end = end_of_month(now, tz)
    events = _events(plans, now, window_end, fee_kobo)

    remaining = {1: 0, 2: 0, 3: 0}
    for e in events:
        if e.rank:
            remaining[e.rank] += e.cost_kobo
    protected = sum(remaining.values())

    sent_by_day = {day_key(now, tz): sent_today_kobo}
    balance = available_kobo
    out = []
    for e in events:
        key = day_key(e.at, tz)
        sent_today = sent_by_day.get(key, 0)
        if e.rank:
            remaining[e.rank] -= e.cost_kobo
            need = sum(remaining[k] for k in range(1, e.rank))
        else:
            need = sum(remaining.values())

        if daily_cap_kobo and sent_today + e.amount_kobo > daily_cap_kobo:
            status = CAP
        elif balance - e.cost_kobo >= need:
            status = PROTECTED if e.rank else SEND
        else:
            status = SHORT if e.rank else WAIT

        if status in GOES_OUT:
            balance -= e.cost_kobo
            sent_by_day[key] = sent_today + e.amount_kobo
        out.append(replace(e, status=status))

    total = sum(e.cost_kobo for e in events)
    return Forecast(
        window_end=window_end,
        events=out,
        protected_kobo=protected,
        free_kobo=available_kobo - protected,
        total_needed_kobo=total,
        top_up_kobo=max(0, total - available_kobo),
        priority_shortfall_kobo=max(0, protected - available_kobo),
        waiting=[e for e in out if e.status == WAIT],
        short=[e for e in out if e.status == SHORT],
        capped=[e for e in out if e.status == CAP],
    )


def decide(*, plan_id: str, at: datetime, amount_kobo: int, plans, available_kobo: int, sent_today_kobo: int,
           fee_kobo, tz: str, daily_cap_kobo: int | None = None) -> Decision:
    """
    Live decision for one due run (used by the worker). Matches what forecast() predicts:
    the money that must stay behind is the cost of higher-priority runs still due after this
    run, up to the end of this run's month.
    """
    plan = next((p for p in plans if p.id == plan_id), None)
    rank = plan.priority_rank if plan else None
    cost = amount_kobo + fee_for(fee_kobo, amount_kobo)

    guarded = [p for p in plans if p.id != plan_id and p.priority_rank and (rank is None or p.priority_rank < rank)]
    reserved = sum(e.cost_kobo for e in _events(guarded, at + timedelta(microseconds=1), end_of_month(at, tz), fee_kobo))

    if daily_cap_kobo and sent_today_kobo + amount_kobo > daily_cap_kobo:
        return Decision(False, reserved, "daily_cap", sent_today_kobo + amount_kobo - daily_cap_kobo)
    if available_kobo < cost:
        return Decision(False, reserved, "insufficient_funds", cost - available_kobo)
    if available_kobo - cost < reserved:
        return Decision(False, reserved, "protected_for_priorities", reserved - (available_kobo - cost))
    return Decision(True, reserved)
