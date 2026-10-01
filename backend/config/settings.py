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
    "TRANSFER_FEE_KOBO": int(env("TRANSFER_FEE_KOBO", "5000")),
    "LATE_SEND_WINDOW_HOURS": int(env("LATE_SEND_WINDOW_HOURS", "6")),
    "MATERIALISE_DAYS": 35,
    "WORKER_TICK_SECONDS": int(env("WORKER_TICK_SECONDS", "30")),
    # TSQ retry schedule for transfers still pending, in seconds. After the last one the run is flagged for review.
    "TSQ_BACKOFF_SECONDS": [30, 120, 600, 3600],
    "PAYMENT_PROVIDER": env("PAYMENT_PROVIDER", "mock"),
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
