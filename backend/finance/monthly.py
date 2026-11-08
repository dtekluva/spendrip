"""
The monthly Finance email ("Your October in money"), sent from the worker on the 1st from 9 AM local, after the month
outlook. Covers the month that just ended: what went out, where it went, against take-home pay, the and Kobo's take. Only for people who sent at least one drip that month and haven't turned it off; once per person per month.
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
from notifications.emails import wordmark
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
    app = settings.SPENDRIP["PUBLIC_APP_URL"].rstrip("/")
    first = user.first_name.title() or "there"

    # plain text
    text = [f"Hi {first}, here's your {month} in money.", "",
            f"Sent: {N(last['sent_kobo'])} in {last['drips']} drips" + (f" ({change_txt})" if change_txt else ""),
            f"Fees: {N(last['fees_kobo'])} · Added: {N(last['topups_kobo'])}", "", "Where it went:"]
    text += [f"  {c['emoji']} {c['label']}: {N(v)} ({round(v * 100 / total)}%)" for c, v in rows]
    if f.salary:
        text += ["", f"Against your take-home pay of {N(f.salary)}: a normal month plans {round(f.normal_total * 100 / f.salary)}% of it."]
    text += ["", "Kobo's take:", take["summary"], *[f"- {t['title']}: {t['body']}" for t in take["suggestions"][:3]],
             "", f"Open Finance: {app}/finance", "", "General information, not financial advice. Turn this email off in Settings → Notifications."]

    # html: table layout and inline styles so Gmail and Outlook keep the look. Icons are the app's, as PNGs (see
    # design/icons/email/assets.py), served from EMAIL_ASSET_BASE.
    A = settings.EMAIL_ASSET_BASE
    INK, BODY, MUTED, LINE = "#0E1233", "#3b4070", "#8a8fb5", "#ECEEF7"
    DISPLAY = "Unbounded,'Arial Black',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    pct = lambda v: round(v * 100 / total)
    bar = "".join(f'<td style="height:12px;background:{COLOURS.get(c["key"], "#B8BECC")};width:{max(pct(v), 1)}%;'
                  f'{"border-left:2px solid #ffffff;" if i else ""}"></td>' for i, (c, v) in enumerate(rows))
    rows_html = "".join(
        f'<tr><td style="padding:10px 12px 10px 0;border-bottom:1px solid {LINE};width:32px">'
        f'<img src="{A}/cat-{c["key"]}.png" width="32" height="32" alt="" style="display:block;border:0"></td>'
        f'<td style="padding:10px 0;border-bottom:1px solid {LINE};font-size:15px;font-weight:600;color:{INK}">{escape(c["label"])}</td>'
        f'<td style="padding:10px 0;border-bottom:1px solid {LINE};font-size:15px;font-weight:800;color:{INK};text-align:right;white-space:nowrap">{N(v)}</td>'
        f'<td style="padding:10px 0 10px 12px;border-bottom:1px solid {LINE};font-size:13px;color:{MUTED};text-align:right;width:40px">{pct(v)}%</td></tr>'
        for c, v in rows)
    tips = "".join(
        f'<tr><td style="padding:16px 12px 0 0;width:26px;vertical-align:top">'
        f'<div style="width:26px;height:26px;line-height:26px;border-radius:13px;background:#2436F2;color:#ffffff;font-size:13px;font-weight:800;text-align:center">{i}</div></td>'
        f'<td style="padding:16px 0 0;vertical-align:top"><div style="font-size:15px;font-weight:800;color:{INK};margin:2px 0 3px">{escape(t["title"])}</div>'
        f'<div style="font-size:14px;line-height:1.5;color:{BODY}">{escape(t["body"])}</div></td></tr>'
        for i, t in enumerate(take["suggestions"][:3], 1))
    salary = (f'<p style="margin:16px 0 0;font-size:14px;color:{BODY}">Against your take-home pay of <b>{N(f.salary)}</b>, a normal month plans '
              f'<b>{round(f.normal_total * 100 / f.salary)}%</b> of it.</p>') if f.salary else ""
    side = lambda k, v, sub: (f'<div style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{MUTED}">{k}</div>'
                              f'<div style="font-size:18px;font-weight:800;color:{INK};margin-top:2px">{v}</div>'
                              f'<div style="font-size:12px;color:{BODY}">{sub}</div>')
    sent_sub = escape(change_txt) or f"{last['drips']} drips"
    stats = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EEF0FF;border-radius:18px"><tr>'
             f'<td style="padding:18px 20px;vertical-align:top">'
             f'<div style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#2436F2">Sent</div>'
             f'<div style="font-family:{DISPLAY};font-size:34px;font-weight:800;letter-spacing:-1px;line-height:1.15;color:{INK};margin-top:4px">{N(last["sent_kobo"])}</div>'
             f'<div style="font-size:13px;color:{BODY};margin-top:2px">{sent_sub}</div></td>'
             f'<td style="padding:18px 20px;vertical-align:top;width:38%;border-left:1px solid #D9DDFB">'
             f'{side("Fees", N(last["fees_kobo"]), "all fees in")}<div style="height:12px"></div>{side("Added", N(last["topups_kobo"]), "top-ups")}</td>'
             f'</tr></table>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#F4F5FB;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:28px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:28px;overflow:hidden;box-shadow:0 12px 40px -18px rgba(14,18,51,.35)">
<tr><td style="background:#0B1040;padding:22px 28px 26px">
{wordmark()}
<div style="font-family:{DISPLAY};font-size:26px;font-weight:800;letter-spacing:-.6px;line-height:1.2;color:#ffffff;margin-top:22px">Your {month} in money</div>
</td></tr>
<tr><td style="padding:24px 28px 8px">
<p style="margin:0 0 16px;font-size:16px;line-height:1.5;color:{BODY}">Hi {escape(first)}, here's where your money went in {month}.</p>
{stats}
<div style="font-family:{DISPLAY};font-size:17px;font-weight:800;letter-spacing:-.3px;color:{INK};margin:28px 0 12px">Where it went</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-radius:6px;overflow:hidden"><tr>{bar}</tr></table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:6px">{rows_html}</table>
{salary}
</td></tr>
<tr><td style="padding:20px 28px 0">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFF8E1;border-radius:22px"><tr><td style="padding:20px 22px 22px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:12px;vertical-align:middle"><img src="{A}/kobo-happy.png" width="40" height="47" alt="" style="display:block;border:0"></td>
<td style="vertical-align:middle;font-family:{DISPLAY};font-size:17px;font-weight:800;letter-spacing:-.3px;color:{INK}">Kobo's take</td></tr></table>
<p style="margin:14px 0 4px;font-size:15px;line-height:1.55;color:{INK}">{escape(take["summary"])}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{tips}</table>
</td></tr></table>
</td></tr>
<tr><td style="padding:24px 28px 26px"><a href="{app}/finance" style="display:inline-block;background:#0B1040;color:#FFD23F;font-weight:800;font-size:15px;text-decoration:none;padding:14px 26px;border-radius:14px">Open Finance</a></td></tr>
<tr><td style="padding:0 28px 26px;font-size:12px;line-height:1.5;color:{MUTED}">General information, not financial advice{". Kobo's take is written by AI from your numbers" if take.get("source") == "ai" else ""}.
Don't want this email? Turn off <i>Monthly money report</i> in Settings → Notifications.</td></tr>
</table></td></tr></table></body></html>"""
    return subject, "\n".join(text), html


# Each category's colour, as in the app's Finance charts (design/icons/manifest.json: the category's plan, its chart or hue).
COLOURS = {"housing": "#7650F2", "food": "#FFC81F", "transport": "#2F44F5", "bills": "#0C93B0", "education": "#FF8A3D", "health": "#E5484D",
           "staff": "#C2620F", "family": "#F2427E", "giving": "#B8336A", "savings": "#0E9F70", "personal": "#5F6576", "other": "#5F6576"}
