"""All money is integer kobo (₦1 = 100 kobo). Never use floats for balances."""
from decimal import ROUND_HALF_UP, Decimal

DEFAULT_FEE_KOBO = 5_000  # ₦50 per outward transfer


def naira(amount) -> int:
    """Naira (int, str or Decimal) to kobo."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_naira(kobo: int) -> Decimal:
    return (Decimal(kobo) / 100).quantize(Decimal("0.01"))


def format_naira(kobo: int) -> str:
    value = Decimal(kobo) / 100
    if kobo % 100:
        return f"₦{value:,.2f}"
    return f"₦{int(value):,}"
