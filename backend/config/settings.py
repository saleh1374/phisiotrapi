"""
Django settings for the Freebuff Physiotherapy Clinic backend.

Environment variables are read from a `.env` file placed next to this file
(see `.env.example` for the full list of supported variables).
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the backend/.env file (if present).
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    # Local
    "accounts.apps.AccountsConfig",
    "appointments.apps.AppointmentsConfig",
    "videos.apps.VideosConfig",
    "academy.apps.AcademyConfig",
    "news.apps.NewsConfig",
    "siteconfig.apps.SiteconfigConfig",
    "admin_api.apps.AdminApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# PostgreSQL is the production engine (per project spec). For quick local
# development without a running PostgreSQL instance, set DATABASE_ENGINE=sqlite3.
# ---------------------------------------------------------------------------
if os.getenv("DATABASE_ENGINE", "postgres") == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "physio_clinic"),
            "USER": os.getenv("POSTGRES_USER", "physio"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "physio"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Authentication — custom phone-number based user model
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Password hashing: Argon2 first (memory-hard), fall back to PBKDF2.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ---------------------------------------------------------------------------
# Django REST Framework + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Security: max 5 OTP / login attempts per minute (brute-force guard).
        "otp": "5/min",
        "login": "5/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Datasets are small (doctors, videos, courses, news) — plain lists are
    # simpler for the frontend. Add per-view pagination if the data grows.
    "PAGE_SIZE": None,
}

# ---------------------------------------------------------------------------
# Google OAuth (sign in with Google) — empty client ID disables the button.
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

SIMPLE_JWT = {
    # Spec: access token valid for 24h, refresh token for 7 days.
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
}

# ---------------------------------------------------------------------------
# CORS — the Next.js frontend talks to this API from a different origin.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Celery (used later for scheduled tasks: news RSS reader, SMS, ...)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TIMEZONE = "Asia/Tehran"
CELERY_BEAT_SCHEDULE = {
    "fetch-news-every-6-hours": {
        "task": "news.tasks.fetch_news_task",
        "schedule": 21600.0,  # Every 6 hours (6 * 60 * 60)
    },
}

# ---------------------------------------------------------------------------
# Internationalization — Persian primary, UTC storage
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# OTP settings
# ---------------------------------------------------------------------------
# How long an OTP code stays valid (seconds).
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
# Maximum wrong attempts before an OTP code is invalidated.
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
# When True, the generated OTP is printed to the console instead of sending SMS
# (development mode). Set OTP_SMS_BACKEND=console|kavenegar to choose.
OTP_SMS_BACKEND = os.getenv("OTP_SMS_BACKEND", "console")