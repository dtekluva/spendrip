"""
Spending categories for plans and expenses. A plan's category is set by the person, or guessed from its name and the
recipient's name; AI fills in names the rules don't recognise (see ai.py).
"""
from __future__ import annotations

import re

# key: (label, emoji, group) — group is the salary-split slice: needs | family | savings | wants
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "housing": ("Rent and housing", "🏠", "needs"),
    "food": ("Feeding and household", "🍲", "needs"),
    "transport": ("Transport and fuel", "⛽", "needs"),
    "bills": ("Bills and data", "💡", "needs"),
    "education": ("School and allowances", "🎓", "needs"),
    "health": ("Health", "💊", "needs"),
    "staff": ("Staff and household help", "🧑🏾‍🍳", "needs"),
    "family": ("Family support", "💛", "family"),
    "giving": ("Giving and church", "🙏🏾", "family"),
    "savings": ("Savings", "🐷", "savings"),
    "personal": ("Personal spending", "🙋🏾", "wants"),
    "other": ("Other", "💸", "wants"),
}

GROUPS = {"needs": "Needs", "family": "Family and giving", "savings": "Savings", "wants": "Everything else"}
# The split on spendrip.com/salary-split-nigeria/: 40% needs, 30% family and wants, 20% savings, 10% buffer.
GUIDE = {"needs": 40, "family_wants": 30, "savings": 20, "buffer": 10}

RULES: list[tuple[str, str]] = [
    ("housing", r"\b(rent|house rent|landlord|service charge|accommodation|apartment|estate dues?)\b"),
    ("food", r"\b(feeding|food|upkeep|market|groceries|grocery|foodstuff|soup|chop|kitchen|house ?keeping|provisions?|cooking gas|gas)\b"),
    ("transport", r"\b(fuel|petrol|diesel|transport|uber|bolt|taxi|keke|okada|car)\b"),
    ("bills", r"\b(data|airtime|electricity|light|nepa|prepaid|dstv|gotv|startimes|netflix|internet|wifi|fibre|fiber|subscription|phone bill|water bill|bills?)\b"),
    ("education", r"\b(school|fees|tuition|allowance|pocket money|books|lesson|exam|jamb|waec|university|student)\b"),
    ("health", r"\b(drugs?|hospital|hmo|pharmacy|clinic|medical|medicine|health|gym)\b"),
    ("staff", r"\b(driver|nanny|cook|chef|gateman|security|cleaner|house ?help|maid|gardener|staff|payroll|salary|salaries|wages)\b"),
    ("giving", r"\b(tithe|offering|church|mosque|zakat|sadaqah|charity|donation|seed)\b"),
    ("savings", r"\b(savings?|save|emergency|investment|invest|piggy|future|rainy day|goal)\b"),
    ("family", r"\b(mum|mom|mama|mummy|mother|dad|daddy|papa|father|parents?|sister|brother|sis|bro|aunty|auntie|uncle|grandma|grandpa|"
               r"granny|nne|baba|iya|family|in-?law|wife|husband|my baby|babe|son|daughter|cousin|nephew|niece|koko|twin)\b"),
    ("personal", r"\b(me|myself|personal|my week|pocket|fun|treat|shopping|enjoyment)\b"),
]


def guess(*names: str) -> str | None:
    text = " ".join(n for n in names if n).lower()
    for key, pattern in RULES:
        if re.search(pattern, text):
            return key
    return None


def plan_category(plan, ai_guesses: dict | None = None) -> tuple[str, str]:
    """(category, source) where source is user | rule | ai | none."""
    if plan.category in CATEGORIES:
        return plan.category, "user"
    who = plan.recipient.label if plan.recipient_id and plan.recipient else ""
    g = guess(plan.label, who)
    if not g and plan.recipient_id and plan.recipient and plan.recipient.is_self:
        g = "personal"
    if not g and plan.kind == "group":
        g = "staff" if re.search(r"(pay|staff|salar|wage)", plan.label.lower()) else None
    if g:
        return g, "rule"
    if ai_guesses and ai_guesses.get(str(plan.pk)) in CATEGORIES:
        return ai_guesses[str(plan.pk)], "ai"
    return "other", "none"


def info(key: str) -> dict:
    label, emoji, group = CATEGORIES.get(key, CATEGORIES["other"])
    return {"key": key, "label": label, "emoji": emoji, "group": group}
