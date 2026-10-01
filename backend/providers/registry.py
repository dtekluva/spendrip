"""Pick providers from settings. Mocks are module-level singletons so web dev tools and the worker in one process share state."""
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def get_payment_provider():
    name = settings.SPENDRIP["PAYMENT_PROVIDER"]
    if name == "liberty":
        from .liberty import LibertyProvider
        c = settings.LIBERTY
        return LibertyProvider(base_url=c["BASE_URL"], email=c["EMAIL"], password=c["PASSWORD"], api_key=c["API_KEY"],
                               source_account=c["SOURCE_ACCOUNT"], mode=c["MODE"], timeout=c["TIMEOUT_SECONDS"])
    from .mock import DbMockPaymentProvider
    return DbMockPaymentProvider()


@lru_cache(maxsize=1)
def get_messenger():
    from .mock import MockMessenger
    return MockMessenger()  # real WhatsApp provider comes later (docs/PLAN.md §2)


@lru_cache(maxsize=1)
def get_kyc_provider():
    from .mock import MockKycProvider
    return MockKycProvider()
