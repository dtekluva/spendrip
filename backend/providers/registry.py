"""Pick providers from settings. Mocks are module-level singletons so web dev tools and the worker in one process share state."""
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def get_payment_provider():
    """Accounts provider: SpenDrip account numbers (virtual accounts) and checking incoming transfers."""
    name = settings.SPENDRIP["PAYMENT_PROVIDER"]
    if name == "liberty":
        from .liberty import LibertyProvider
        c = settings.LIBERTY
        return LibertyProvider(base_url=c["BASE_URL"], email=c["EMAIL"], password=c["PASSWORD"], api_key=c["API_KEY"],
                               source_account=c["SOURCE_ACCOUNT"], mode=c["MODE"], timeout=c["TIMEOUT_SECONDS"])
    from .mock import DbMockPaymentProvider
    return DbMockPaymentProvider()


def _paystack_client():
    from .paystack import PaystackClient
    c = settings.PAYSTACK
    return PaystackClient(secret_key=c["SECRET_KEY"], base_url=c["BASE_URL"], timeout=c["TIMEOUT_SECONDS"])


@lru_cache(maxsize=1)
def get_payout_provider():
    """Payout provider: sending money and checking account names. Defaults to the accounts provider."""
    name = settings.SPENDRIP["PAYOUT_PROVIDER"] or settings.SPENDRIP["PAYMENT_PROVIDER"]
    if name == "paystack":
        from .paystack import PaystackProvider
        return PaystackProvider(_paystack_client())
    return get_payment_provider() if name == settings.SPENDRIP["PAYMENT_PROVIDER"] else _named(name)


def _named(name):
    if name == "liberty":
        from .liberty import LibertyProvider
        c = settings.LIBERTY
        return LibertyProvider(base_url=c["BASE_URL"], email=c["EMAIL"], password=c["PASSWORD"], api_key=c["API_KEY"],
                               source_account=c["SOURCE_ACCOUNT"], mode=c["MODE"], timeout=c["TIMEOUT_SECONDS"])
    from .mock import DbMockPaymentProvider
    return DbMockPaymentProvider()


@lru_cache(maxsize=1)
def get_card_gateway():
    """Card top-ups: Paystack when a key is set, a test checkout in dev, otherwise none."""
    if settings.PAYSTACK["SECRET_KEY"]:
        from .paystack import PaystackCardGateway
        return PaystackCardGateway(_paystack_client())
    if settings.SPENDRIP["DEV_TOOLS"]:
        from .mock import MockCardGateway
        return MockCardGateway(settings.SPENDRIP["PUBLIC_APP_URL"])
    return None


@lru_cache(maxsize=1)
def get_messenger():
    from .mock import MockMessenger
    return MockMessenger()  # real WhatsApp provider comes later (docs/PLAN.md §2)


@lru_cache(maxsize=1)
def get_kyc_provider():
    from .mock import MockKycProvider
    return MockKycProvider()


def get_name_checker():
    """Who answers "whose account is this?". The live-key Paystack checker when PAYSTACK_LIVE_NAME_CHECKS
    is on, otherwise the payout provider."""
    c = settings.PAYSTACK
    if c.get("NAME_CHECK_SECRET_KEY"):
        from .paystack import PaystackClient, PaystackNameChecker
        return PaystackNameChecker(PaystackClient(secret_key=c["NAME_CHECK_SECRET_KEY"], base_url=c["BASE_URL"],
                                                  timeout=c["TIMEOUT_SECONDS"]))
    return get_payout_provider()
