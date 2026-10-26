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
MIN_GAP = timedelta(minutes=10)  # don't call the AI again sooner than this, even if numbers change

SYSTEM = """You are Kobo, the friendly money guide inside SpenDrip, a Nigerian app that sends people's scheduled transfers
(drips) to family, staff and themselves. You write a short monthly money summary and practical suggestions.

Rules you must follow:
- Use ONLY numbers that appear in the facts. Never invent or estimate a figure that isn't there. Amounts are in naira; write them like ₦45,000.
- Warm, plain Nigerian English. No jargon, no shaming, no lecturing. Family support is normal and good; help people plan it.
- This is general information, not financial advice. Never tell the person to buy a specific investment product, never name a
  company or fund, never promise or predict returns, never call anything "the best". You may explain general ideas (pay yourself
  first, an emergency fund, moving money to their own savings account, government savings like T-bills in general terms).
- Facts only cover money planned or sent through SpenDrip (and costs they told us they pay elsewhere), not all their spending. Don't claim otherwise.
- Be specific to their plans and numbers. Suggest changes SpenDrip can do: change a plan's frequency, add a plan, make one a priority,
  add their salary, set up a savings drip, use Auto-fill on payday.
Reply with JSON only."""

PROMPT = """Facts about this person's money (JSON):
{facts}

Return exactly this JSON shape:
{{"summary": "2 or 3 sentences, at most 60 words, about their month and what stands out",
  "suggestions": [{{"title": "at most 6 words", "body": "at most 35 words, specific, using their numbers", "kind": "fees|plan|savings|salary|family|general"}}],
  "categories": {{"<plan id>": "<one of {keys}>"}}}}
Give 2 to 4 suggestions, most useful first. In "categories", include only plans whose category is "unknown"."""


def facts_hash(facts: dict) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()


def latest(user) -> FinanceSnapshot | None:
    return FinanceSnapshot.objects.filter(user=user).order_by("-created_at").first()


def insights(user, facts: dict, *, force: bool = False) -> tuple[dict | None, str]:
    """(ai dict or None, status) — status is fresh | cached | stale | error."""
    h = facts_hash(facts)
    snap = latest(user)
    if snap and snap.facts_hash == h and not force:
        return snap.ai, "cached"
    if snap and not force and timezone.now() - snap.created_at < MIN_GAP:
        return snap.ai, "stale"
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
