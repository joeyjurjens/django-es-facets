INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_elasticsearch_dsl",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SECRET_KEY = "fake-key"

# Will be set by pytest
ELASTICSEARCH_DSL = {}
