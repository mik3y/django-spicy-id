import os

SECRET_KEY = "test"

INSTALLED_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_spicy_id",
    "django_spicy_id.tests",
)

# The CI matrix (see .github/workflows/test.yml) selects the database backend
# and connection details through these environment variables; plain local runs
# default to in-memory sqlite.
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite3")

DATABASES = {
    "default": {
        "ENGINE": f"django.db.backends.{DB_BACKEND}",
        "NAME": os.environ.get("DB_NAME", ":memory:" if DB_BACKEND == "sqlite3" else ""),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", ""),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
)

ROOT_URLCONF = "django_spicy_id.tests.urls"

# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.contrib.auth.context_processors.auth",
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.i18n",
#                 "django.template.context_processors.media",
#                 "django.template.context_processors.static",
#                 "django.template.context_processors.tz",
#                 "django.contrib.messages.context_processors.messages",
#             ]
#         },
#     }
# ]

USE_TZ = True
