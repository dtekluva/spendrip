"""
Kobo's take: an AI-written summary and suggestions for the Finance report, plus categories for plan names the rules
don't recognise. Built only from the numbers in Facts.for_ai(); cached until those numbers change.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta

from django.utils import timezone

from providers.claude import text_json

from . import categories as cats
from .models import FinanceSnapshot

log = logging.getLogger(__name__)
# Cost guards. Kobo re-reads the month only when something that matters changed (see STABLE), and never more than:
AUTO_GAP = timedelta(minutes=10)  # automatically, after a real change
REFRESH_GAP = timedelta(hours=1)  # when the person taps Refresh
DAILY_LIMIT = 4  # AI runs per person per day, whatever happens
RULES_VERSION = 2
# The facts that decide whether Kobo needs to read again: plans, pay, costs, categories and the month. Not the balance or
# each drip going out, which change all the time.
STABLE = ("month", "salary_monthly", "normal_month_total", "normal_month_by_category", "plans", "paid_elsewhere",
          "missing_essentials", "paused_everything", "autofill_available")

SYSTEM = """You are Kobo, the friendly money guide inside SpenDrip, a Nigerian app that sends people's scheduled transfers
(drips) to family, staff and themselves. You write a short monthly money summary and practical suggestions.

Rules you must follow:
- Use ONLY numbers that appear in the facts. Never invent or estimate a figure that isn't there. Amounts are in naira; write them like ₦45,000.
- Warm, plain Nigerian English. No jargon, no shaming, no lecturing. Family support is normal and good; help people plan it.
- This is general information, not financial advice. Never tell the person to buy a specific investment product, never name a
  company or fund, never promise or predict returns, never call anything "the best". You may explain general ideas (pay yourself
  first, an emergency fund, moving money to their own savings account, government savings like T-bills in general terms).
- Facts only cover money planned or sent through SpenDrip (and costs they told us they pay elsewhere), not all their spending. Don't claim otherwise.
- Never suggest sending money less often than weekly, or merging weekly drips into monthly ones: dripping money in small,
  regular pieces is the point of SpenDrip. Only mention frequency changes that appear in fee_savings.
- Be specific to their plans and numbers. Suggest changes SpenDrip can do: change a plan's frequency, add a plan, make one a priority,
  add their salary, set up a savings drip, and (only if autofill_available is true) use Auto-fill on payday.
Reply with JSON only."""

PROMPT = """Facts about this person's money (JSON):
{facts}

Return exactly this JSON shape:
{{"summary": "2 or 3 sentences, at most 60 words, about their month and what stands out",
  "suggestions": [{{"title": "at most 6 words", "body": "at most 35 words, specific, using their numbers", "kind": "fees|plan|savings|salary|family|general"}}],
  "categories": {{"<plan id>": "<one of {keys}>"}}}}
Give 2 to 4 suggestions, most useful first. In "categories", include only plans whose category is "unknown"."""


def facts_hash(facts: dict) -> str:
    stable = {k: facts.get(k) for k in STABLE}
    stable["month"] = str(facts.get("today", ""))[:7]
    stable["rules"] = RULES_VERSION  # bump when the prompt or the fee rules change, so old takes are read again
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def runs_today(user) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return FinanceSnapshot.objects.filter(user=user, created_at__gte=start).count()


def latest(user) -> FinanceSnapshot | None:
    return FinanceSnapshot.objects.filter(user=user).order_by("-created_at").first()


def insights(user, facts: dict, *, force: bool = False) -> tuple[dict | None, str]:
    """(ai dict or None, status) — fresh | cached | stale | too_soon | limit | error. Only "fresh" called the AI."""
    h = facts_hash(facts)
    snap = latest(user)
    age = timezone.now() - snap.created_at if snap else None
    if snap and snap.facts_hash == h and not force:
        return snap.ai, "cached"
    if snap and not force and age < AUTO_GAP:
        return snap.ai, "stale"
    if snap and force and age < REFRESH_GAP:
        return snap.ai, "too_soon"
    if runs_today(user) >= DAILY_LIMIT:
        return (snap.ai if snap else None), "limit"
    try:
        out = text_json(PROMPT.format(facts=json.dumps(facts, ensure_ascii=False, default=str), keys=", ".join(cats.CATEGORIES)), system=SYSTEM)
    except Exception as e:  # the report still works without the AI
        log.warning("finance insights failed for user %s: %s", user.pk, e)
        return (snap.ai if snap else None), "error"
    ai = {
        "summary": str(out.get("summary", ""))[:500],
        "suggestions": [{"title": str(x.get("title", ""))[:60], "body": str(x.get("body", ""))[:300],
                         "kind": x.get("kind") if x.get("kind") in ("fees", "plan", "savings", "salary", "family", "general") else "general"}
                        for x in (out.get("suggestions") or [])[:4] if isinstance(x, dict) and x.get("body")],
        "categories": {str(k): v for k, v in (out.get("categories") or {}).items() if v in cats.CATEGORIES},
    }
    FinanceSnapshot.objects.create(user=user, month=facts.get("today", "")[:7], facts_hash=h, ai=ai)
    return ai, "fresh"
