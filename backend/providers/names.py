"""Account name checks, with a short memory so each account costs one check, and clear reasons when a check fails."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .base import NameEnquiryError, ProviderError
from .models import ResolvedAccount
from .registry import get_name_checker

log = logging.getLogger(__name__)
REMEMBER_FOR = timedelta(days=30)


@dataclass(frozen=True)
class Name:
    account_name: str
    test_name: bool = False  # a made-up name, only in test mode when the real check isn't available


class NameCheckFailed(Exception):
    def __init__(self, message: str, code: str, status: int = 400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _test_mode() -> bool:
    ps = getattr(settings, "PAYSTACK", {})
    return settings.SPENDRIP["DEV_TOOLS"] and ps.get("MODE") != "live" and not ps.get("NAME_CHECK_SECRET_KEY")


def resolve(nip_bank_code: str, account_number: str) -> Name:
    known = ResolvedAccount.objects.filter(nip_bank_code=nip_bank_code, account_number=account_number,
                                           resolved_at__gte=timezone.now() - REMEMBER_FOR).first()
    if known:
        return Name(known.account_name)
    provider = get_name_checker()
    try:
        r = provider.name_enquiry(nip_bank_code, account_number)
    except NameEnquiryError as e:
        if e.kind == "limit":
            log.warning("name check limit: %s", e)
            if _test_mode():
                from .mock import MockPaymentProvider
                return Name(MockPaymentProvider().name_enquiry(nip_bank_code, account_number).account_name, test_name=True)
            raise NameCheckFailed("We've checked a lot of accounts in a short time. Try again in a few minutes.", "lookup_busy", 429)
        if e.kind == "unsupported":
            raise NameCheckFailed(str(e), "bank_unsupported")
        raise NameCheckFailed(str(e), "lookup_failed")
    except ValueError as e:  # older providers raise plain ValueError for "not found"
        raise NameCheckFailed(str(e) or "We couldn't find that account. Check the number and bank.", "lookup_failed")
    except ProviderError as e:
        log.warning("name check unavailable: %s", e)
        raise NameCheckFailed("We can't reach the bank to check this account right now. Try again in a minute.", "lookup_unavailable", 503)
    ResolvedAccount.objects.update_or_create(nip_bank_code=nip_bank_code, account_number=account_number,
                                             defaults={"account_name": r.account_name, "provider": provider.name,
                                                       "resolved_at": timezone.now()})
    return Name(r.account_name)
