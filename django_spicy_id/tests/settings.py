SECRET_KEY = "test"

INSTALLED_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_spicy_id",
    "django_spicy_id.tests",
)

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
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
