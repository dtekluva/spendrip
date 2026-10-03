"""Message copy. Written as fixed templates because business-initiated WhatsApp messages need pre-approved templates."""
from engine import format_naira


def recipient_paid(*, recipient_label: str, amount_kobo: int, bank: str, last4: str, sender_first_name: str) -> str:
    return (f"Hi {recipient_label} 💛 {format_naira(amount_kobo)} just landed in your {bank} account (••{last4}). "
            f"Sent by {sender_first_name} via SpenDrip.")


def self_paid(*, emoji: str, label: str, amount_kobo: int, recipient_label: str, bank: str, last4: str) -> str:
    return f"{emoji} {label}: {format_naira(amount_kobo)} sent to {recipient_label} ({bank} ••{last4}) ✅"


def self_skipped(*, emoji: str, label: str, amount_kobo: int, reason: str, short_by_kobo: int) -> str:
    why = {
        "protected_for_priorities": "to keep your priorities safe",
        "insufficient_funds": "because your balance is too low",
        "daily_cap": "because it would go over your daily limit",
        "paused": "because everything is paused",
    }.get(reason, "")
    tail = f" Top up {format_naira(short_by_kobo)} to send it." if short_by_kobo and reason != "daily_cap" else ""
    return f"{emoji} {label} ({format_naira(amount_kobo)}) is waiting {why}.{tail}".replace("  ", " ")


GROUP_WHY = {
    "protected_for_priorities": "to keep your priorities safe",
    "insufficient_funds": "because your balance can't cover everyone yet",
    "daily_cap": "because it would go over your daily limit",
}


def group_waiting(*, emoji: str, label: str, people: int, cost_kobo: int, reason: str, short_by_kobo: int, hours: int) -> str:
    tail = (f" Add {format_naira(short_by_kobo)} in the next {hours} hours and everyone is paid together."
            if short_by_kobo and reason != "daily_cap" else f" Raise your daily limit in the next {hours} hours to send it.")
    return f"{emoji} {label} ({people} people, {format_naira(cost_kobo)}) is waiting {GROUP_WHY.get(reason, '')}.{tail}".replace("  ", " ")


def group_skipped(*, emoji: str, label: str, people: int, cost_kobo: int, reason: str) -> str:
    why = {"paused": "because it's paused", "missed": "because it's too late to send it today"}.get(reason, GROUP_WHY.get(reason, ""))
    return f"{emoji} {label} ({people} people, {format_naira(cost_kobo)}) didn't go out {why}. Nobody on it was paid.".replace("  ", " ")


def group_done(*, emoji: str, label: str, paid: int, people: int, amount_kobo: int) -> str:
    if paid == people:
        return f"{emoji} {label}: all {people} people paid, {format_naira(amount_kobo)} ✅"
    return (f"{emoji} {label}: {paid} of {people} paid ({format_naira(amount_kobo)}). "
            "The rest didn't go through and their money is back in your balance.")


def self_failed(*, emoji: str, label: str, amount_kobo: int) -> str:
    return f"{emoji} {label} ({format_naira(amount_kobo)}) didn't go through. The money is back in your balance."


def self_missed(*, emoji: str, label: str, amount_kobo: int) -> str:
    return f"{emoji} {label} ({format_naira(amount_kobo)}) was missed because it's too late to send it today. Tap to send it now."


def self_topped_up(*, amount_kobo: int) -> str:
    return f"{format_naira(amount_kobo)} added to your SpenDrip balance."
