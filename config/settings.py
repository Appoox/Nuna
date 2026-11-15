"""
Django settings for the fact tracker.

One settings file for every environment. Anything that differs between
machines (debug mode, secret key, database, host names) is read from
environment variables, so the same code runs in development and production.

In development the variables come from the `.env` file, which Docker Compose
passes to the container (see compose.yaml). `.env.example` lists them all.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# The repository root: the folder that contains manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers for reading environment variables
# ---------------------------------------------------------------------------


def env(name, default=None):
    """
    Return the environment variable `name`.

    If it is not set, return `default`. If there is no default either, stop
    with a clear error, so a missing setting is noticed at start-up and not
    later as a confusing failure.
    """
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"The environment variable {name} is not set.")
    return value


def env_bool(name, default=False):
    """Read a true/false environment variable ("1", "true", "yes", "on" mean true)."""
    return str(env(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    """Read a comma-separated environment variable as a list, dropping blanks."""
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

# Used to sign sessions and tokens. No default on purpose: it must be set
# explicitly, and must be long, random and private in production.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# Debug mode shows detailed error pages. Off unless switched on, so a
# production machine that forgets the variable stays safe.
DEBUG = env_bool("DJANGO_DEBUG", default=False)

# Host names this site may be served under, comma-separated.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

# Origins (scheme + host) trusted for form posts over HTTPS, comma-separated.
# Empty in development; needed once the site sits behind a proxy.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    # Wagtail: the editing interface and everything it needs.
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    # Libraries Wagtail depends on.
    "modelcluster",
    "taggit",
    "django_filters",
    # Django itself.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        # Project-wide templates would go in a top-level "templates" folder.
        "DIRS": [BASE_DIR / "templates"],
        # Also look for templates inside each installed app.
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


# ---------------------------------------------------------------------------
# Database: PostgreSQL
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        # "db" is the name of the Postgres service in compose.yaml.
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

# Primary keys are 64-bit integers unless a model says otherwise.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

# Rules applied when an editor sets a password.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Language and time
# ---------------------------------------------------------------------------

# Language of the editing interface. The content itself is stored in both
# English and Malayalam, in separate model fields.
LANGUAGE_CODE = "en"

# Dates and times are shown in Indian Standard Time...
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
# ...and stored in the database in UTC.
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files (CSS, JavaScript) and uploaded files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
# Where `manage.py collectstatic` gathers static files for production.
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded files are kept on the server's disk, in this folder.
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

STORAGES = {
    # Uploaded files: plain files on disk. To move them to object storage
    # later, only this backend has to change.
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    # Static files: Django's standard storage.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ---------------------------------------------------------------------------
# Wagtail
# ---------------------------------------------------------------------------

# Name shown in the Wagtail admin. A placeholder until the site has a name.
WAGTAIL_SITE_NAME = env("WAGTAIL_SITE_NAME", "Fact tracker")

# Full address of the site, used for links in emails Wagtail sends to editors.
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", "http://localhost:8000")

# Search inside the Wagtail admin uses the database: no separate search server.
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}

# File types accepted by Wagtail's own document library. This does not limit
# the evidence files stored by this project, which get their own rules.
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "key", "odt", "pdf", "pptx", "rtf", "txt", "xlsx", "zip"]
