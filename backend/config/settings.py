import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "accounts",
    "providers",
    "ledger",
    "drips",
    "notifications",
    "seasons",
    "seo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", "postgresql://spendrip:spendrip@localhost:5434/spendrip"),
        # Serverless (Vercel) opens a connection per invocation: use the provider's pooled URL and 0 here.
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-ng"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True  # serve admin assets without a collectstatic step (serverless-friendly)
try:
    STATIC_ROOT.mkdir(exist_ok=True)
except OSError:
    pass  # read-only filesystem (serverless); finders serve the files instead
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["api.permissions.Unlocked"],
    "EXCEPTION_HANDLER": "api.errors.handle",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
CORS_ALLOW_CREDENTIALS = True

# The React app calls the API through a same-origin /api proxy (Vite in dev, a Vercel rewrite in
# production), so session cookies and CSRF work like a normal same-site app.
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", "http://localhost:5173").split(",")
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # stay signed in on a device for 90 days; the app locks after idle time
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ---- SpenDrip ----
SPENDRIP = {
    # What each drip costs on top of its amount (engine/fees.py): SpenDrip's fee, plus the payout provider's
    # transfer charge and the ₦50 stamp duty on ₦10,000+, both passed through at cost.
    "TRANSFER_FEE_KOBO": int(env("TRANSFER_FEE_KOBO", "5000")),  # SpenDrip's own fee
    "GROUP_FEE_KOBO": int(env("GROUP_FEE_KOBO", "10000")),  # SpenDrip's fee for a whole group payout (₦100), however many people
    "STAMP_DUTY_KOBO": int(env("STAMP_DUTY_KOBO", "5000")),
    "STAMP_DUTY_FROM_KOBO": int(env("STAMP_DUTY_FROM_KOBO", "1000000")),
    "PASS_THROUGH_TRANSFER_FEES": env_bool("PASS_THROUGH_TRANSFER_FEES", True),
    # Live-money safety rails.
    "PAYOUTS_ENABLED": env_bool("PAYOUTS_ENABLED", True),  # off = no drip is sent; due ones wait (and miss after the late window)
    "DEFAULT_DAILY_CAP_KOBO": int(env("DEFAULT_DAILY_CAP_KOBO", "100000000")),  # ₦1,000,000 a day for new accounts
    # Bank-transfer funding needs real virtual accounts (Liberty). Off = no account number is issued or shown; cards only.
    "BANK_TRANSFER_FUNDING": env_bool("BANK_TRANSFER_FUNDING", True),
    # Limits for accounts verified with an ID photo + live selfies (no government database check yet).
    # Raised above CBN Tier-1 levels on 3 Oct 2026 for group payouts; government ID checks (Dojah) should come next.
    "TIER1_MAX_BALANCE_KOBO": int(env("TIER1_MAX_BALANCE_KOBO", "200000000")),  # ₦2,000,000
    "TIER1_MAX_DRIP_KOBO": int(env("TIER1_MAX_DRIP_KOBO", "50000000")),  # ₦500,000 per transfer
    "LATE_SEND_WINDOW_HOURS": int(env("LATE_SEND_WINDOW_HOURS", "6")),
    "MATERIALISE_DAYS": 35,
    "WORKER_TICK_SECONDS": int(env("WORKER_TICK_SECONDS", "30")),
    # TSQ retry schedule for transfers still pending, in seconds. After the last one the run is flagged for review.
    "TSQ_BACKOFF_SECONDS": [30, 120, 600, 3600],
    "PAYMENT_PROVIDER": env("PAYMENT_PROVIDER", "mock"),  # accounts: account numbers + incoming transfers
    "PAYOUT_PROVIDER": env("PAYOUT_PROVIDER", ""),  # sending money + name checks; empty = same as PAYMENT_PROVIDER
    # Where the React app lives, for links back into it (e.g. after card checkout).
    "PUBLIC_APP_URL": env("PUBLIC_APP_URL", "http://localhost:5173"),
    "MESSENGER": env("MESSENGER", "mock"),
    "KYC_PROVIDER": env("KYC_PROVIDER", "mock"),
    # Dev-only helpers (simulate top-up, demo user) are on only when this is true.
    "DEV_TOOLS": env_bool("SPENDRIP_DEV_TOOLS", DEBUG),
    # Lock the app after this much idle time; unlocking needs Face ID or the PIN.
    "IDLE_LOCK_SECONDS": int(env("IDLE_LOCK_SECONDS", "600")),
    "OTP_TTL_SECONDS": 600,
    "OTP_RESEND_SECONDS": 30,
    "OTP_MAX_ATTEMPTS": 5,
    # Shared secret for the scheduled tick (Vercel Cron sends "Authorization: Bearer <CRON_SECRET>").
    "CRON_SECRET": env("CRON_SECRET", ""),
    # Lets the Liberty webhook be authenticated with a shared secret header, on top of verifying each event with Liberty.
    "WEBHOOK_SECRET": env("LIBERTY_WEBHOOK_SECRET", ""),
}

WEBAUTHN = {
    "RP_ID": env("WEBAUTHN_RP_ID", "localhost"),
    "RP_NAME": "SpenDrip",
    "ORIGIN": env("WEBAUTHN_ORIGIN", "http://localhost:5173"),
}

# Paystack keys. Test keys (TEST_PAYSTACK_*) are used unless PAYSTACK_MODE=live, and live keys are
# refused while dev tools are on, so a laptop can never move real money by accident.
PAYSTACK_MODE = env("PAYSTACK_MODE", "test" if DEBUG else "live")
if PAYSTACK_MODE == "live":
    _ps_secret, _ps_public = env("PAYSTACK_SECRET_KEY", ""), env("PAYSTACK_PUBLIC_KEY", "")
    if _ps_secret and SPENDRIP["DEV_TOOLS"]:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("Live Paystack keys can't be used while SPENDRIP_DEV_TOOLS is on (it shows sign-in codes on screen). Turn dev tools off, or use PAYSTACK_MODE=test.")
else:
    _ps_secret, _ps_public = env("TEST_PAYSTACK_SECRET_KEY", ""), env("TEST_PAYSTACK_PUBLIC_KEY", "")
    if _ps_secret.startswith("sk_live_"):
        _ps_secret = ""  # a live key put under the TEST_ name is ignored, never used

# Account name checks can use the LIVE key even while everything else is in test mode: /bank/resolve only
# reads a name and moves no money, and test mode allows just 3 real-bank checks a day. The live key is then
# held by a checker that can do nothing but name lookups (providers.paystack.PaystackNameChecker).
_live_names = env_bool("PAYSTACK_LIVE_NAME_CHECKS", False)
_name_key = env("PAYSTACK_SECRET_KEY", "") if _live_names else ""
if _live_names and not _name_key.startswith("sk_live_"):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("PAYSTACK_LIVE_NAME_CHECKS=true needs a live PAYSTACK_SECRET_KEY (sk_live_…).")

PAYSTACK = {
    "MODE": PAYSTACK_MODE,
    "NAME_CHECK_SECRET_KEY": _name_key,  # set only when name checks run live
    "SECRET_KEY": _ps_secret,  # never sent to the browser
    "PUBLIC_KEY": _ps_public,
    "BASE_URL": env("PAYSTACK_BASE_URL", "https://api.paystack.co"),
    # True: the payer covers Paystack's card fee (shown before paying). False: SpenDrip absorbs it.
    "PASS_CARD_FEES": env_bool("PAYSTACK_PASS_CARD_FEES", True),
    # How people can pay on Paystack's checkout: card, bank (pay from a bank account) and bank_transfer (pay with transfer).
    # Paystack shows only the ones also switched on in its dashboard.
    "CHANNELS": [c.strip() for c in env("PAYSTACK_CHANNELS", "card,bank,bank_transfer").split(",") if c.strip()],
    "TIMEOUT_SECONDS": 20,
}

# Encrypts saved-card tokens at rest. Set its own value in production (any long random string).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", SECRET_KEY)

LIBERTY = {
    "BASE_URL": env("LIBERTY_BASE_URL", "https://banking.libertypayng.com"),
    "EMAIL": env("LIBERTY_EMAIL", ""),
    "PASSWORD": env("LIBERTY_PASSWORD", ""),
    "API_KEY": env("LIBERTY_API_KEY", ""),
    "SOURCE_ACCOUNT": env("LIBERTY_SOURCE_ACCOUNT", ""),
    "MODE": env("LIBERTY_MODE", "LIVE"),
    "TIMEOUT_SECONDS": 20,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

# ---- Email ----
# With a Mailgun key, mail goes out through Mailgun's HTTP API; without one it's printed to the console.
MAILGUN = {
    "API_KEY": env("MAILGUN_API_KEY", ""),
    "DOMAIN": env("MAILGUN_DOMAIN", "mg.spendrip.com"),
    "API_BASE": env("MAILGUN_API_BASE", "https://api.mailgun.net").rstrip("/"),
}
EMAIL_BACKEND = ("notifications.mailgun.MailgunBackend" if MAILGUN["API_KEY"]
                 else "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "SpenDrip <hello@mg.spendrip.com>")
# Images used in emails (Kobo etc.) are served by the landing site, landing/email/.
# Monthly Google Search Console report (python manage.py seo_report). The key is a service account's JSON key, base64-encoded.
SEARCH_CONSOLE = {
    "SITE": env("GSC_SITE", "sc-domain:spendrip.com"),
    "CREDENTIALS_B64": env("GSC_CREDENTIALS_B64", ""),
    "CREDENTIALS_FILE": env("GSC_CREDENTIALS_FILE", ""),
    "REPORT_TO": env("SEO_REPORT_TO", "hello@spendrip.com"),
}

EMAIL_ASSET_BASE = env("EMAIL_ASSET_BASE", "https://spendrip.com/email").rstrip("/")


# ---- Claude (reads ID photos and checks selfies are clear when KYC_PROVIDER=live) ----
ANTHROPIC = {
    "API_KEY": env("ANTHROPIC_API_KEY", ""),
    "MODEL": env("ANTHROPIC_KYC_MODEL", "claude-sonnet-5-5"),
    "BASE_URL": env("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
}
