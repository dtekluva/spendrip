"""
The Finance report: a list of sections, each included only when it applies, so the app can lay out whatever comes back.

Every section is {"kind", "id", "title", "priority", "span", "data"}. kind picks the app's renderer; span is 1 (narrow)
or 2 (wide on big screens); a lower priority sits higher. New kinds can be added without breaking older apps (they skip
kinds they don't know).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from drips.models import Plan, Run
from drips.services import typical_month
from ledger import services as ledger
from ledger.models import Inflow

from . import categories as cats
from .models import Expense, FinanceProfile, SavingsOption

MONTHS_BACK = 6
ESSENTIALS = ("housing", "food")  # what most households pay; we ask if they're missing


def _local(user, dt: datetime) -> datetime:
    return dt.astimezone(ZoneInfo(user.tz or "Africa/Lagos"))


def _month_starts(now_local: datetime, n: int) -> list[datetime]:
    first = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    out = [first]
    for _ in range(n - 1):
        out.insert(0, (out[0] - timedelta(days=1)).replace(day=1))
    return out


def _pct(a: int, b: int) -> int | None:
    return round((a - b) * 100 / b) if b else None


class Facts:
    """Everything the sections (and the AI) are built from, computed once."""

    def __init__(self, user, now: datetime | None = None, ai_categories: dict | None = None):
        self.user, self.now = user, now or timezone.now()
        self.local = _local(user, self.now)
        self.profile = FinanceProfile.objects.filter(user=user).first()
        self.salary = self.profile.salary_kobo if self.profile and self.profile.salary_kobo else None
        self.dismissed = set(self.profile.dismissed if self.profile else [])
        self.plans = {str(p.pk): p for p in Plan.objects.filter(user=user).exclude(status=Plan.Status.DELETED).select_related("recipient")}
        self.cat_of = {pid: cats.plan_category(p, ai_categories) for pid, p in self.plans.items()}
        self.expenses = list(Expense.objects.filter(user=user))
        self.balance = ledger.balance(user).available_kobo
        self._months()
        self._normal_month()

    def _months(self):
        starts = _month_starts(self.local, MONTHS_BACK)
        self.month_keys = [f"{s:%Y-%m}" for s in starts]
        since = starts[0]
        sent = {k: {"sent_kobo": 0, "fees_kobo": 0, "drips": 0, "by_cat": defaultdict(int)} for k in self.month_keys}
        for r in Run.objects.filter(user=self.user, status=Run.Status.SUCCESSFUL, scheduled_for__gte=since).values(
                "plan_id", "amount_kobo", "fee_kobo", "scheduled_for"):
            k = f"{_local(self.user, r['scheduled_for']):%Y-%m}"
            if k in sent:
                m = sent[k]
                m["sent_kobo"] += r["amount_kobo"]
                m["fees_kobo"] += r["fee_kobo"]
                m["drips"] += 1
                m["by_cat"][self.cat_of.get(str(r["plan_id"]), ("other", ""))[0]] += r["amount_kobo"]
        topups = defaultdict(int)
        for i in Inflow.objects.filter(user=self.user, status=Inflow.Status.CREDITED, credited_at__gte=since).values("amount_kobo", "credited_at"):
            topups[f"{_local(self.user, i['credited_at']):%Y-%m}"] += i["amount_kobo"]
        self.months = [{"month": k, **{x: v for x, v in sent[k].items() if x != "by_cat"}, "by_cat": dict(sent[k]["by_cat"]),
                        "topups_kobo": topups.get(k, 0)} for k in self.month_keys]

    def _normal_month(self):
        t = typical_month(self.user, self.now)
        self.typical = t
        by_cat, rows = defaultdict(int), []
        for r in t["plans"]:
            key, src = self.cat_of.get(r["plan_id"], ("other", "none"))
            by_cat[key] += r["total_kobo"]
            rows.append({**r, "category": key, "category_source": src})
        for e in self.expenses:
            by_cat[e.category if e.category in cats.CATEGORIES else "other"] += e.monthly_kobo
        self.plan_rows = rows
        self.by_cat = dict(by_cat)
        self.normal_total = sum(by_cat.values())
        self.by_group = defaultdict(int)
        for k, v in self.by_cat.items():
            self.by_group[cats.info(k)["group"]] += v

    def _rule_cat(self, pid: str) -> str:
        p = self.plans.get(pid)
        key, src = cats.plan_category(p) if p else ("other", "none")
        return key if src != "none" else "unknown"

    # ------------------------------------------------------------ derived
    def missing(self) -> list[str]:
        have = set(self.by_cat)
        return [k for k in ESSENTIALS if k not in have and f"missing:{k}" not in self.dismissed]

    def last_full(self) -> tuple[dict, dict]:
        return self.months[-2], self.months[-3]

    def for_ai(self) -> dict:
        last, before = self.last_full()
        return {
            "today": f"{self.local:%Y-%m-%d}", "currency": "NGN (amounts in naira)", "country": "Nigeria",
            "balance": self.balance // 100, "salary_monthly": self.salary // 100 if self.salary else None,
            "normal_month_total": self.normal_total // 100,
            "normal_month_by_category": {cats.info(k)["label"]: v // 100 for k, v in sorted(self.by_cat.items(), key=lambda x: -x[1])},
            # Rule/user categories only (not the AI's own guesses), so applying the AI's answer doesn't change these facts.
            "plans": [{"id": r["plan_id"], "name": r["label"], "category": self._rule_cat(r["plan_id"]),
                       "per_month": r["total_kobo"] // 100, "frequency": self.plans[r["plan_id"]].frequency if r["plan_id"] in self.plans else ""}
                      for r in self.plan_rows],
            "paid_elsewhere": [{"name": e.label, "category": e.category, "per_month": e.monthly_kobo // 100} for e in self.expenses],
            "sent_by_month": [{"month": m["month"], "sent": m["sent_kobo"] // 100, "fees": m["fees_kobo"] // 100, "topped_up": m["topups_kobo"] // 100}
                              for m in self.months],
            "last_month_vs_before_pct": _pct(last["sent_kobo"], before["sent_kobo"]),
            "missing_essentials": [cats.info(k)["label"] for k in self.missing()],
            "paused_everything": self.user.paused_all,
            "autofill_available": bool(getattr(settings, "AUTOFILL_ENABLED", False)),
            "guide": "40% needs, 30% family and wants, 20% savings, 10% buffer (SpenDrip's salary-split guide)",
        }


def _section(kind, sid, title, priority, data, span=1):
    return {"kind": kind, "id": sid, "title": title, "priority": priority, "span": span, "data": data}


def build(user, now: datetime | None = None, ai: dict | None = None) -> dict:
    f = Facts(user, now, (ai or {}).get("categories"))
    s = []
    this, (last, before) = f.months[-1], f.last_full()

    s.append(_section("headline", "glance", "This month so far", 10, {
        "month": this["month"], "sent_kobo": this["sent_kobo"], "fees_kobo": this["fees_kobo"], "drips": this["drips"],
        "topups_kobo": this["topups_kobo"], "last_month": last["month"], "last_sent_kobo": last["sent_kobo"],
        "last_change_pct": _pct(last["sent_kobo"], before["sent_kobo"]), "balance_kobo": f.balance}))

    for k in f.missing():
        c = cats.info(k)
        s.append(_section("missing", f"missing:{k}", f"{c['label']} isn't here", 20, {
            "category": k, "label": c["label"], "emoji": c["emoji"],
            "examples": {"housing": "rent, service charge", "food": "feeding money, market, foodstuff"}[k]}))

    if f.normal_total:
        rows = sorted(({**cats.info(k), "kobo": v, "pct": round(v * 100 / f.normal_total)} for k, v in f.by_cat.items()), key=lambda x: -x["kobo"])
        s.append(_section("breakdown", "breakdown", "Where your money goes", 30, {
            "total_kobo": f.normal_total, "rows": rows, "plans": f.plan_rows, "categories": [cats.info(k) for k in cats.CATEGORIES],
            "expenses": [{"id": e.pk, "label": e.label, "category": e.category, "amount_kobo": e.amount_kobo, "every": e.every,
                          "monthly_kobo": e.monthly_kobo} for e in f.expenses]}, span=2))

    if f.salary:
        g = f.by_group
        groups = [{"key": k, "label": cats.GROUPS[k], "kobo": g.get(k, 0), "pct": round(g.get(k, 0) * 100 / f.salary)} for k in ("needs", "family", "savings", "wants")]
        s.append(_section("salary", "salary", "Against your salary", 40, {
            "salary_kobo": f.salary, "planned_kobo": f.normal_total, "left_kobo": f.salary - f.normal_total,
            "planned_pct": round(f.normal_total * 100 / f.salary), "groups": groups, "guide": cats.GUIDE}))
    else:
        s.append(_section("salary", "salary", "Against your salary", 40, {"salary_kobo": None, "guide": cats.GUIDE}))

    with_sends = [m for m in f.months if m["sent_kobo"]]
    if len(with_sends) >= 2:
        s.append(_section("trend", "trend", "Your last 6 months", 60, {"months": [{
            "month": m["month"], "sent_kobo": m["sent_kobo"], "fees_kobo": m["fees_kobo"], "topups_kobo": m["topups_kobo"],
            "by_group": {grp: sum(v for k, v in m["by_cat"].items() if cats.info(k)["group"] == grp) for grp in cats.GROUPS}} for m in f.months],
            "last_change_pct": _pct(last["sent_kobo"], before["sent_kobo"])}, span=2))
    else:
        s.append(_section("trend", "trend", "Your last 6 months", 60, {"months": None, "note": "Your trend appears once you've sent drips in two different months."}, span=2))

    fam = f.by_group.get("family", 0)
    if fam:
        s.append(_section("family", "family", "Family and giving", 70, {
            "kobo": fam, "pct_of_month": round(fam * 100 / f.normal_total) if f.normal_total else 0,
            "pct_of_salary": round(fam * 100 / f.salary) if f.salary else None,
            "people": sorted({r["label"] for r in f.plan_rows if cats.info(r["category"])["group"] == "family"})}))

    if f.typical["need_kobo"]:
        cover = f.balance / f.typical["need_kobo"]
        s.append(_section("next", "next", "Next month", 80, {
            "month": f.typical["month"], "need_kobo": f.typical["need_kobo"], "balance_kobo": f.balance,
            "cover": round(cover, 2), "lasts_until": f"{(f.local + timedelta(days=cover * 30.4)):%Y-%m-%d}",
            "short_kobo": max(0, f.typical["need_kobo"] - f.balance)}))

    has_savings = f.by_cat.get("savings", 0) > 0
    s.append(_section("savings", "savings", "Ways to save", 90, {
        "has_savings_plan": has_savings,
        "options": [{"name": o.name, "kind": o.kind, "summary": o.summary, "rate_text": o.rate_text, "checked_on": o.checked_on,
                     "source_name": o.source_name, "source_url": o.source_url, "risk": o.risk, "access": o.access}
                    for o in SavingsOption.objects.filter(active=True)],
        "disclaimer": "General information, not financial advice. Rates change; check with the provider before you decide."}, span=2))

    s.append(_section("insights", "insights", "Kobo's take", 5, ai_insights(ai) if ai else rule_insights(f), span=2))
    s.sort(key=lambda x: x["priority"])
    return {"sections": s, "facts": f}


# ---------------------------------------------------------------- insights without AI (fallback, and while AI loads)

def rule_insights(f: Facts) -> dict:
    tips = []
    for k in f.missing():
        tips.append({"title": f"Add {cats.info(k)['label'].lower()}", "body": "Most homes pay this every month. Add it, even if you pay it "
                     "another way, so your picture of the month is complete.", "kind": "plan"})
    if f.salary and f.by_group.get("savings", 0) * 100 < f.salary * cats.GUIDE["savings"]:
        tips.append({"title": "Pay yourself first", "body": "A drip to your own savings account on payday makes saving automatic. The guide "
                     "suggests about 20% of take-home pay.", "kind": "savings"})
    if not f.salary:
        tips.append({"title": "Add your take-home pay", "body": "See what share of your salary each part of your month takes.", "kind": "salary"})
    last, before = f.last_full()
    ch = _pct(last["sent_kobo"], before["sent_kobo"])
    summary = (f"A normal month for you is about ₦{f.normal_total // 100:,}" + (f", {round(f.normal_total * 100 / f.salary)}% of your take-home pay" if f.salary else "")
               + "." + (f" Last month you sent {'more' if ch > 0 else 'less'} than the month before ({ch:+}%)." if ch else "")) if f.normal_total else \
        "Set up your first plan and Finance will show where your money goes."
    return {"summary": summary, "suggestions": tips[:4], "source": "rules"}


def ai_insights(ai: dict) -> dict:
    return {"summary": ai.get("summary", ""), "suggestions": ai.get("suggestions", [])[:4], "source": "ai"}
