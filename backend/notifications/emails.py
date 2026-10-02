"""The emails SpenDrip sends. Each one has a plain-text and an HTML version."""
import logging
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

log = logging.getLogger(__name__)


def _html(heading: str, paragraphs: list[str], button: tuple[str, str] | None = None) -> str:
    body = "".join(
        f'<p style="margin:6px 0 20px;font-size:34px;font-weight:800;letter-spacing:8px;color:#0B1040;font-family:Menlo,Consolas,monospace">{p}</p>'
        if p.isdigit() and len(p) == 6 else
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.55;color:#3b4070">{escape(p)}</p>' for p in paragraphs)
    cta = ""
    if button:
        label, url = button
        cta = (f'<p style="margin:22px 0 6px"><a href="{escape(url)}" style="display:inline-block;background:#0B1040;color:#FFD23F;'
               f'font-weight:800;font-size:16px;text-decoration:none;padding:14px 26px;border-radius:14px">{escape(label)}</a></p>')
    return f"""<!doctype html><html><body style="margin:0;background:#F4F5FB;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:32px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:24px;overflow:hidden">
<tr><td style="background:#0B1040;padding:22px 28px;font-size:24px;font-weight:800;letter-spacing:-.5px;color:#ffffff">spendrip<span style="color:#FFD23F">.</span></td></tr>
<tr><td style="padding:30px 28px 26px">
<h1 style="margin:0 0 16px;font-size:24px;line-height:1.2;color:#0E1233">{escape(heading)}</h1>{body}{cta}
</td></tr>
<tr><td style="padding:0 28px 26px;font-size:13px;color:#8a8fb5">SpenDrip · Money that shows up on time.</td></tr>
</table></td></tr></table></body></html>"""


def send(to: str, subject: str, heading: str, paragraphs: list[str], button: tuple[str, str] | None = None,
         fail_silently: bool = True) -> bool:
    text = "\n\n".join([heading, *paragraphs] + ([f"{button[0]}: {button[1]}"] if button else []) + ["SpenDrip · Money that shows up on time."])
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    msg.attach_alternative(_html(heading, paragraphs, button), "text/html")
    try:
        return msg.send(fail_silently=fail_silently) == 1
    except Exception:
        log.exception("email to %s failed", to)
        if not fail_silently:
            raise
        return False


def send_raw(to: str, subject: str, text: str, html: str, fail_silently: bool = True) -> bool:
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    msg.attach_alternative(html, "text/html")
    try:
        return msg.send(fail_silently=fail_silently) == 1
    except Exception:
        log.exception("email to %s failed", to)
        if not fail_silently:
            raise
        return False


def waitlist_joined(entry) -> bool:
    hi = f"Hi {entry.name}," if entry.name else "Hi there,"
    return send(entry.contact, "You're on the SpenDrip waitlist 💧", "You're on the list!", [
        hi,
        "Thanks for joining the SpenDrip waitlist. We're letting people in a few at a time, and we'll email you the moment your spot is ready.",
        "Soon you'll be able to set your payments once (fuel every Friday, upkeep every morning, Mum at month-end) and let SpenDrip send every one on time.",
    ])


def waitlist_invite(entry, fail_silently: bool = True) -> bool:
    hi = f"Hi {entry.name}," if entry.name else "Hi there,"
    url = settings.SPENDRIP["PUBLIC_APP_URL"]
    return send(entry.contact, "Your SpenDrip invite is here 🎉", "You're in!", [
        hi,
        "Your spot is ready. Sign up with your NIN, a photo of your ID and a quick selfie. It takes about two minutes.",
        "Then set up your first drip and let SpenDrip handle the rest.",
    ], button=("Open SpenDrip", url), fail_silently=fail_silently)


def sign_in_code(to: str, code: str, purpose: str) -> bool:
    if purpose == "signup":
        subject, heading, first = f"{code} is your SpenDrip code", "Confirm your email", "Use this code to finish creating your SpenDrip account:"
    else:
        subject, heading, first = f"{code} is your SpenDrip sign-in code", "Sign in to SpenDrip", "Use this code to sign in:"
    return send(to, subject, heading, [first, code, "It expires in 10 minutes. Never share it with anyone, including SpenDrip staff.",
                                       "Didn't ask for this? You can ignore this email."])


# ---------------------------------------------------------------- "your drip landed"

OPENERS = ["Boom! 💥", "Nailed it! 🎯", "Right on time ⏰", "Another one lands 💧", "Done and dusted ✨"]


def delivered_context(run, balance_kobo: int) -> dict:
    """Everything the delivery email shows, as plain values (so a sample can be rendered without a real run)."""
    from zoneinfo import ZoneInfo

    from drips.models import Run
    plan, r, user = run.plan, run.plan.recipient, run.user
    tz = ZoneInfo(user.tz or "Africa/Lagos")
    when = (run.completed_at or run.scheduled_for).astimezone(tz)
    nxt = (Run.objects.filter(user=user, status=Run.Status.SCHEDULED, scheduled_for__gt=run.scheduled_for)
           .exclude(pk=run.pk).select_related("plan").order_by("scheduled_for").first())
    return {
        "first_name": user.first_name.title(), "emoji": plan.emoji, "label": plan.label, "amount_kobo": run.amount_kobo,
        "fee_kobo": run.fee_kobo, "fee_lines": run.fee_parts.lines(), "to_self": r.is_self, "recipient_label": r.label, "account_name": r.verified_account_name.title(),
        "bank": r.bank_name, "last4": r.account_number[-4:], "when": when, "reference": run.provider_ref or str(run.pk)[:8].upper(),
        "balance_kobo": balance_kobo, "seed": run.pk.int if hasattr(run.pk, "int") else hash(str(run.pk)),
        "next": {"emoji": nxt.plan.emoji, "label": nxt.plan.label, "amount_kobo": nxt.amount_kobo,
                 "when": nxt.scheduled_for.astimezone(tz)} if nxt else None,
    }


def _when(dt) -> str:
    return dt.strftime("%a %-d %b, %-I:%M %p").replace("AM", "am").replace("PM", "pm")


def render_delivered(c: dict) -> tuple[str, str, str]:
    """(subject, text, html) for a delivered drip. Table layout + inline styles so Gmail/Outlook keep the look."""
    from engine import format_naira as N
    e = escape
    opener = OPENERS[c["seed"] % len(OPENERS)]
    who = "you" if c["to_self"] else c["recipient_label"]
    amount = N(c["amount_kobo"])
    subject = f"{c['emoji']} {amount} just landed for {who}!"
    headline = "You just got paid! 🎉" if c["to_self"] else f"{who} just got paid! 🎉"
    preheader = f"{amount} landed in {c['account_name']}'s {c['bank']} account. Balance: {N(c['balance_kobo'])}."
    app = settings.SPENDRIP["PUBLIC_APP_URL"]
    kobo = f"{settings.EMAIL_ASSET_BASE}/kobo-celebrate.png"
    hi = f"Hi {c['first_name']}," if c["first_name"] else "Hi there,"
    nxt = c.get("next")

    rows = [("Drip", f"{c['emoji']} {c['label']}"), ("To", f"{c['account_name']}<br><span style=\"color:#6b7099;font-weight:600\">{e(c['bank'])} ••{e(c['last4'])}</span>"),
            ("Landed", _when(c["when"]))]
    rows += [(line["label"], N(line["amount_kobo"])) for line in c.get("fee_lines") or [{"label": "Fees", "amount_kobo": c["fee_kobo"]}]]
    rows += [("Reference", c["reference"])]
    row_html = "".join(
        f'<tr><td style="padding:11px 0;border-top:1px solid #EEF0F8;color:#6b7099;font-size:14px;width:38%">{k}</td>'
        f'<td style="padding:11px 0;border-top:1px solid #EEF0F8;color:#0E1233;font-size:15px;font-weight:700;text-align:right">{v if k == "To" else e(v)}</td></tr>'
        for k, v in rows)
    next_html = (f'<tr><td style="padding:0 28px 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EEF0FF;border-radius:16px">'
                 f'<tr><td style="padding:14px 18px;font-size:14px;color:#2a2f66"><b style="color:#2436F2">Next up:</b> {e(nxt["emoji"])} {e(nxt["label"])} · '
                 f'<b>{N(nxt["amount_kobo"])}</b> on {e(_when(nxt["when"]))}</td></tr></table></td></tr>') if nxt else ""

    html = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#F4F5FB;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:28px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:28px;overflow:hidden;box-shadow:0 12px 40px -18px rgba(14,18,51,.35)">
 <tr><td style="background:#0B1040;padding:20px 28px">
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-size:24px;font-weight:800;letter-spacing:-.6px;color:#ffffff">spendrip<span style="color:#FFD23F">.</span></td>
    <td align="right"><span style="display:inline-block;background:#12B283;color:#ffffff;font-size:12px;font-weight:800;letter-spacing:.06em;padding:6px 12px;border-radius:999px">✓ DELIVERED</span></td>
   </tr></table>
 </td></tr>
 <tr><td style="background:#FFF4CC;border-bottom:4px solid #FFD23F;padding:26px 28px 24px" align="center">
   <img src="{kobo}" width="150" height="141" alt="Kobo, the SpenDrip drop, celebrating" style="display:block;border:0;margin:0 auto 6px">
   <div style="font-size:15px;font-weight:800;color:#0B1040;opacity:.75;letter-spacing:.02em">{e(opener)}</div>
   <div style="font-size:46px;line-height:1.05;font-weight:800;letter-spacing:-1.5px;color:#0B1040;margin:6px 0 4px">{amount}</div>
   <div style="font-size:19px;font-weight:800;color:#0B1040">{e(headline)}</div>
 </td></tr>
 <tr><td style="padding:24px 28px 6px;font-size:16px;line-height:1.55;color:#3b4070">
   {e(hi)} your <b style="color:#0E1233">{e(c['emoji'])} {e(c['label'])}</b> drip went out right on schedule and the bank has confirmed it. Nothing for you to do. 🙌
 </td></tr>
 <tr><td style="padding:10px 28px 18px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{row_html}</table></td></tr>
 <tr><td style="padding:0 28px 14px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0B1040;border-radius:18px">
   <tr><td style="padding:16px 20px;color:#B6BCEB;font-size:13px;font-weight:700;letter-spacing:.08em">BALANCE NOW</td>
       <td style="padding:16px 20px;color:#FFD23F;font-size:24px;font-weight:800;letter-spacing:-.5px" align="right">{N(c['balance_kobo'])}</td></tr></table></td></tr>
 {next_html}
 <tr><td align="center" style="padding:18px 28px 30px">
   <a href="{e(app)}" style="display:inline-block;background:#0B1040;color:#FFD23F;font-size:16px;font-weight:800;text-decoration:none;padding:15px 30px;border-radius:16px">Open SpenDrip →</a>
 </td></tr>
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px"><tr><td style="padding:18px 20px;font-size:12px;line-height:1.6;color:#8a8fb5" align="center">
 You're getting this because drip emails are on. Turn them off any time in <b>Profile → Email me when a drip lands</b>.<br>
 SpenDrip 💧 Money that shows up on time.
</td></tr></table>
</td></tr></table></body></html>"""

    text = "\n".join([
        f"{opener} {amount} just landed for {who}.", "",
        f"{hi} your {c['emoji']} {c['label']} drip went out on schedule and the bank has confirmed it.", "",
        f"To: {c['account_name']} ({c['bank']} ••{c['last4']})", f"Landed: {_when(c['when'])}",
        *[f"{line['label']}: {N(line['amount_kobo'])}" for line in c.get("fee_lines") or []],
        f"Reference: {c['reference']}", f"Balance now: {N(c['balance_kobo'])}",
        *([f"Next up: {nxt['emoji']} {nxt['label']} · {N(nxt['amount_kobo'])} on {_when(nxt['when'])}"] if nxt else []), "",
        f"Open SpenDrip: {app}", "", "Turn these off in Profile → Email me when a drip lands.",
    ])
    return subject, text, html


def drip_delivered_email(run, balance_kobo: int) -> dict:
    subject, text, html = render_delivered(delivered_context(run, balance_kobo))
    return {"subject": subject, "text": text, "html": html}


def sample_delivered(first_name: str = "Ada") -> dict:
    """A realistic example for previews and test sends."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Africa/Lagos")).replace(second=0, microsecond=0)
    return {"first_name": first_name, "emoji": "💛", "label": "Mum", "amount_kobo": 3_000_000, "fee_kobo": 12_500, "to_self": False,
            "fee_lines": [{"label": "SpenDrip fee", "amount_kobo": 5_000}, {"label": "Transfer fee (Paystack)", "amount_kobo": 2_500},
                          {"label": "Stamp duty", "amount_kobo": 5_000}],
            "recipient_label": "Mum", "account_name": "Ngozi Okafor", "bank": "OPay", "last4": "6357", "when": now,
            "reference": "SDP-7F3K2Q", "balance_kobo": 15_495_000, "seed": 0,
            "next": {"emoji": "⛽", "label": "Fuel", "amount_kobo": 4_000_000, "when": (now + timedelta(days=2)).replace(hour=14, minute=0)}}
