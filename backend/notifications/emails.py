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


def drip_delivered_email(run, balance_kobo: int) -> dict:
    """Subject and body for "your drip was delivered". Sent through notify() so it goes out once per run."""
    from engine import format_naira
    from zoneinfo import ZoneInfo
    plan, r = run.plan, run.plan.recipient
    who = "you" if r.is_self else r.label
    when = (run.completed_at or run.scheduled_for).astimezone(ZoneInfo(run.user.tz or "Africa/Lagos"))
    return {
        "subject": f"{plan.emoji} {format_naira(run.amount_kobo)} delivered to {who}",
        "heading": f"{plan.label} delivered {plan.emoji}",
        "paragraphs": [
            f"{format_naira(run.amount_kobo)} landed in {r.verified_account_name.title()}'s {r.bank_name} account (••{r.account_number[-4:]}).",
            f"Sent {when.strftime('%-d %b %Y, %-I:%M %p')} · Fee {format_naira(run.fee_kobo)} · Reference {run.provider_ref or str(run.pk)[:8]}",
            f"Your balance is now {format_naira(balance_kobo)}.",
        ],
        "button": ("Open SpenDrip", settings.SPENDRIP["PUBLIC_APP_URL"]),
    }
