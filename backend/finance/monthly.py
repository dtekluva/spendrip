"""
The monthly Finance email ("Your October in money"), sent from the worker on the 1st from 9 AM local, after the month
outlook. Covers the month that just ended: what went out, where it went, against take-home pay, the best fee idea and
Kobo's take. Only for people who sent at least one drip that month and haven't turned it off; once per person per month.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from drips.models import Run
from notifications.models import OutboxMessage
from notifications.services import notify

from . import ai as fin_ai
from . import categories as cats
from . import report

FROM_HOUR = 9  # local; the month outlook goes from 7
LAST_DAY = 3  # if the worker was down on the 1st, still send by the 3rd


def N(kobo: int) -> str:
    return f"₦{kobo / 100:,.0f}"


def candidates(now: datetime) -> list[User]:
    since = now - timedelta(days=40)
    ids = Run.objects.filter(status=Run.Status.SUCCESSFUL, scheduled_for__gte=since).values_list("user_id", flat=True).distinct()
    return list(User.objects.filter(pk__in=ids, kyc_status=User.Kyc.VERIFIED, notify_finance_email=True).exclude(email__isnull=True).exclude(email=""))


def send_finance_emails(now: datetime | None = None) -> int:
    now = now or timezone.now()
    sent = 0
    for u in candidates(now):
        try:
            sent += send_one(u, now)
        except Exception:  # one person's email must never stop the others
            import logging
            logging.getLogger(__name__).exception("finance email failed for user %s", u.pk)
    return sent


def send_one(user: User, now: datetime, *, force: bool = False, to: str | None = None) -> int:
    local = now.astimezone(ZoneInfo(user.tz or "Africa/Lagos"))
    if not force and (local.day > LAST_DAY or (local.day == 1 and local.hour < FROM_HOUR)):
        return 0
    built = report.build(user, now)
    f = built["facts"]
    last, before = f.last_full()
    if not force and not last["sent_kobo"]:
        return 0
    key = f"finance_month:{user.pk}:{last['month']}"
    if not force and OutboxMessage.objects.filter(dedupe_key=key).exists():
        return 0
    # Kobo's take: the cost guards in ai.insights still apply (a new month counts as a real change, so usually one fresh run).
    ai, _ = fin_ai.insights(user, f.for_ai())
    take = report.ai_insights(ai) if ai else report.rule_insights(f)
    subject, text, html = render(user, f, last, before, take)
    notify(user, key=key if not force else f"{key}:test:{now:%H%M%S}", channel=OutboxMessage.Channel.EMAIL, template="finance_month",
           to=to or user.email, body=subject, email={"subject": subject, "text": text, "html": html})
    return 1


def render(user, f: report.Facts, last: dict, before: dict, take: dict) -> tuple[str, str, str]:
    month = datetime.strptime(last["month"], "%Y-%m").strftime("%B")
    prev = datetime.strptime(before["month"], "%Y-%m").strftime("%B")
    change = report._pct(last["sent_kobo"], before["sent_kobo"])
    change_txt = (f"{'▲' if change > 0 else '▼'} {abs(change)}% on {prev}" if change else f"the same as {prev}") if change is not None else ""
    subject = f"📊 Your {month} in money: {N(last['sent_kobo'])} sent"
    rows = sorted(((cats.info(k), v) for k, v in last["by_cat"].items() if v), key=lambda x: -x[1])[:6]
    total = sum(v for _, v in rows) or 1
    ideas = f.fee_savings()[:1]
    app = settings.SPENDRIP["PUBLIC_APP_URL"].rstrip("/")
    first = user.first_name.title() or "there"

    # plain text
    text = [f"Hi {first}, here's your {month} in money.", "",
            f"Sent: {N(last['sent_kobo'])} in {last['drips']} drips" + (f" ({change_txt})" if change_txt else ""),
            f"Fees: {N(last['fees_kobo'])} · Added: {N(last['topups_kobo'])}", "", "Where it went:"]
    text += [f"  {c['emoji']} {c['label']}: {N(v)} ({round(v * 100 / total)}%)" for c, v in rows]
    if f.salary:
        text += ["", f"Against your take-home pay of {N(f.salary)}: a normal month plans {round(f.normal_total * 100 / f.salary)}% of it."]
    if ideas:
        x = ideas[0]
        text += ["", f"Fee idea: send {x['label']} {x['to']} instead of {x['from']} to save about {N(x['saving_kobo'])} a month."]
    text += ["", "Kobo's take:", take["summary"], *[f"- {t['title']}: {t['body']}" for t in take["suggestions"][:3]],
             "", f"Open Finance: {app}/finance", "", "General information, not financial advice. Turn this email off in Settings → Notifications."]

    # html
    def cell(content, align="left", muted=False):
        return f'<td style="padding:7px 0;border-bottom:1px solid #ECEEF7;font-size:14px;text-align:{align};color:{"#8a8fb5" if muted else "#3b4070"}">{content}</td>'
    bar = "".join(f'<td style="height:10px;background:{COLOURS.get(c["key"], "#B8BECC")};width:{max(round(v * 100 / total), 1)}%"></td>' for c, v in rows)
    rows_html = "".join(f"<tr>{cell(escape(c['emoji'] + ' ' + c['label']))}{cell(N(v), 'right')}{cell(str(round(v * 100 / total)) + '%', 'right', True)}</tr>" for c, v in rows)
    tips = "".join(f'<p style="margin:0 0 10px;font-size:14px;line-height:1.5;color:#3b4070"><b style="color:#0E1233">{escape(t["title"])}.</b> {escape(t["body"])}</p>'
                   for t in take["suggestions"][:3])
    salary = (f'<p style="margin:18px 0 0;font-size:14px;color:#3b4070">Against your take-home pay of <b>{N(f.salary)}</b>, a normal month plans '
              f'<b>{round(f.normal_total * 100 / f.salary)}%</b> of it.</p>') if f.salary else ""
    idea = (f'<p style="margin:14px 0 0;padding:12px 14px;background:#EAF8F2;border-radius:12px;font-size:14px;color:#0E5C44">🧾 <b>Fee idea:</b> send '
            f'{escape(ideas[0]["label"])} {ideas[0]["to"]} instead of {ideas[0]["from"]} to save about <b>{N(ideas[0]["saving_kobo"])}</b> a month.</p>') if ideas else ""
    tiles = "".join(
        f'<td style="padding:12px;background:#F4F5FB;border-radius:12px;width:33%"><div style="font-size:12px;color:#8a8fb5">{k}</div>'
        f'<div style="font-size:19px;font-weight:800;color:#0E1233">{v}</div><div style="font-size:12px;color:#3b4070">{s}</div></td>'
        for k, v, s in (("Sent", N(last["sent_kobo"]), escape(change_txt) or f"{last['drips']} drips"),
                        ("Fees", N(last["fees_kobo"]), "all fees in"), ("Added", N(last["topups_kobo"]), "top-ups")))
    html = f"""<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#F4F5FB;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:28px 10px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:22px;overflow:hidden">
<tr><td style="background:#0B1040;padding:20px 26px;font-size:22px;font-weight:800;color:#ffffff">spendrip<span style="color:#FFD23F">.</span>
<span style="font-size:14px;font-weight:600;color:#c9cdf0"> · Your {month} in money</span></td></tr>
<tr><td style="padding:26px">
<p style="margin:0 0 14px;font-size:16px;color:#3b4070">Hi {escape(first)}, here's where your money went in {month}.</p>
<table width="100%" cellpadding="0" cellspacing="6" style="border-collapse:separate;margin:0 -6px"><tr>{tiles}</tr></table>
<h2 style="margin:22px 0 8px;font-size:16px;color:#0E1233">Where it went</h2>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border-radius:6px;overflow:hidden"><tr>{bar}</tr></table>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:8px">{rows_html}</table>
{salary}{idea}
<h2 style="margin:22px 0 8px;font-size:16px;color:#0E1233">💧 Kobo's take</h2>
<p style="margin:0 0 12px;font-size:15px;line-height:1.55;color:#0E1233">{escape(take["summary"])}</p>
{tips}
<p style="margin:22px 0 4px"><a href="{app}/finance" style="display:inline-block;background:#0B1040;color:#FFD23F;font-weight:800;font-size:15px;text-decoration:none;padding:13px 24px;border-radius:14px">Open Finance</a></p>
</td></tr>
<tr><td style="padding:0 26px 24px;font-size:12px;line-height:1.5;color:#8a8fb5">General information, not financial advice{". Kobo's take is written by AI from your numbers" if take.get("source") == "ai" else ""}.
Don't want this email? Turn off <i>Monthly money report</i> in Settings → Notifications.</td></tr>
</table></td></tr></table></body></html>"""
    return subject, "\n".join(text), html


COLOURS = {"housing": "#2F44F5", "food": "#12B283", "transport": "#FFB938", "bills": "#7C5CFF", "education": "#00A3C4", "health": "#FF6B6B",
           "staff": "#C27C00", "family": "#FF4F8B", "giving": "#B5651D", "savings": "#0FA376", "personal": "#8A93A6", "other": "#B8BECC"}
