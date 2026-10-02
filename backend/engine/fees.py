"""What one drip costs on top of its amount, line by line. Pure, so the app, forecast and worker all agree.

- service:    SpenDrip's own fee (₦50).
- provider:   the payout provider's transfer charge, passed through (Paystack: ₦10 up to ₦5,000,
              ₦25 up to ₦50,000, ₦50 above).
- stamp_duty: the government's ₦50 stamp duty on transfers of ₦10,000 and above, passed through.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SERVICE = "service"
PROVIDER = "provider"
STAMP_DUTY = "stamp_duty"
CARD = "card_processing"
LABELS = {SERVICE: "SpenDrip fee", PROVIDER: "Transfer fee (Paystack)", STAMP_DUTY: "Stamp duty", CARD: "Card fee (Paystack)"}

# (up to and including this amount in kobo, fee in kobo); None = everything above
PAYSTACK_TRANSFER_TIERS: tuple[tuple[int | None, int], ...] = ((500_000, 1_000), (5_000_000, 2_500), (None, 5_000))


@dataclass(frozen=True)
class FeeParts:
    service_kobo: int = 0
    provider_kobo: int = 0
    stamp_duty_kobo: int = 0

    @property
    def total_kobo(self) -> int:
        return self.service_kobo + self.provider_kobo + self.stamp_duty_kobo

    def lines(self) -> list[dict]:
        """Non-zero parts, in the order people see them."""
        parts = [(SERVICE, self.service_kobo), (PROVIDER, self.provider_kobo), (STAMP_DUTY, self.stamp_duty_kobo)]
        return [{"kind": k, "label": LABELS[k], "amount_kobo": v} for k, v in parts if v]


@dataclass(frozen=True)
class FeeSchedule:
    service_kobo: int = 5_000
    stamp_duty_kobo: int = 5_000
    stamp_duty_from_kobo: int = 1_000_000
    provider_tiers: tuple[tuple[int | None, int], ...] = field(default=PAYSTACK_TRANSFER_TIERS)

    def provider_fee(self, amount_kobo: int) -> int:
        for up_to, fee in self.provider_tiers:
            if up_to is None or amount_kobo <= up_to:
                return fee
        return 0

    def parts(self, amount_kobo: int) -> FeeParts:
        duty = self.stamp_duty_kobo if self.stamp_duty_kobo and amount_kobo >= self.stamp_duty_from_kobo else 0
        return FeeParts(self.service_kobo, self.provider_fee(amount_kobo), duty)

    def __call__(self, amount_kobo: int) -> int:
        return self.parts(amount_kobo).total_kobo

    def describe(self) -> dict:
        return {"service_kobo": self.service_kobo, "stamp_duty_kobo": self.stamp_duty_kobo,
                "stamp_duty_from_kobo": self.stamp_duty_from_kobo,
                "provider_tiers": [{"up_to_kobo": u, "fee_kobo": f} for u, f in self.provider_tiers]}


def fee_for(fee, amount_kobo: int) -> int:
    """`fee` is either a flat kobo amount or something that maps an amount to its total fee."""
    return fee(amount_kobo) if callable(fee) else fee
