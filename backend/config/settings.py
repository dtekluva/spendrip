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
    "ledger",
    "drips",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        env("DATABASE_URL", "postgresql://spendrip:spendrip@localhost:5434/spendrip"), conn_max_age=60,
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
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
CORS_ALLOW_CREDENTIALS = True

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
