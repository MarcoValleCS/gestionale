"""Configurazione del progetto Gestionale.

Le variabili d'ambiente permettono di usare la stessa codebase in sviluppo
(SQLite, debug attivo) e in produzione su VPS Linux (PostgreSQL, HTTPS).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- Sicurezza
SECRET_KEY = env("DJANGO_SECRET_KEY", "chiave-di-sviluppo-non-utilizzare-in-produzione")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

if env_bool("DJANGO_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False

# ------------------------------------------------------- Difese aggiuntive
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # sessione di 12 ore
# Non riscrivere la sessione a ogni richiesta: con più utenti collegati è una
# scrittura sul database per ogni pagina aperta. La sessione viene salvata solo
# quando cambia davvero. Effetto: la scadenza non si sposta a ogni clic, quindi
# dopo 12 ore dall'accesso occorre rientrare.
SESSION_SAVE_EVERY_REQUEST = False
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB (import Excel)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# Limiti anti-abuso (finestra in secondi): usati da apps.core.middleware
ABUSE_THROTTLE = {
    "login": {"limit": 8, "window": 300},   # 8 tentativi di accesso ogni 5 minuti per IP
    "search": {"limit": 120, "window": 60},  # 120 ricerche al minuto per IP
}

# ------------------------------------------------------------ Email (SMTP)
# Usata per inviare fatture/preventivi; per lo SDI va bene la casella PEC.
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Gestionale <no-reply@example.com>")
EMAIL_IS_CONFIGURED = bool(EMAIL_HOST)
if not EMAIL_HOST:
    # In sviluppo (o senza SMTP configurato) le email finiscono nei log del server
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ------------------------------------------------ Fatturazione elettronica
SDI_PEC_ADDRESS = env("SDI_PEC_ADDRESS", "sdi01@pec.fatturapa.it")

# ------------------------------------------------------------------- App
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.core",
    "apps.contacts",
    "apps.catalog",
    "apps.inventory",
    "apps.sales",
    "apps.purchasing",
    "apps.jobs",
    "apps.billing",
    "apps.hr",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "apps.accounts.middleware.CollaboratorRestrictionMiddleware",
    "apps.core.activity.RegistroAttivitaMiddleware",
    "apps.core.middleware.AbuseThrottleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.company",
                "apps.core.context_processors.tema",
                "apps.core.context_processors.roles",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------- Database
if env("DB_ENGINE", "").lower() in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "gestionale"),
            "USER": env("DB_USER", "gestionale"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    # SQLite, tarato anche per più utenti in contemporanea:
    #  - WAL: i lettori non bloccano chi scrive (e viceversa);
    #  - busy_timeout: attende il blocco invece di fallire subito con
    #    «database is locked»;
    #  - transaction_mode «IMMEDIATE»: il blocco di scrittura viene preso
    #    all'inizio della transazione, così due richieste non possono leggere
    #    lo stesso dato e sovrascriversi (Django lo supporta da 5.1).
    # In produzione su VPS si usa PostgreSQL (vedi docker-compose.yml), che
    # gestisce la concorrenza con blocchi di riga.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "timeout": 20,
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=20000;",
                "transaction_mode": "IMMEDIATE",
            },
            # I test usano un file e non un database in memoria: WAL e
            # busy_timeout non hanno effetto in memoria, quindi i test di
            # concorrenza non riprodurrebbero le condizioni reali.
            "TEST": {"NAME": BASE_DIR / "test_db.sqlite3"},
        }
    }

# ------------------------------------------------------- Autenticazione
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# ------------------------------------------------ Lingua, fuso e formati
LANGUAGE_CODE = "it-it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."

# ------------------------------------------------------ File statici/media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------- Cache
# Cache su file: condivisa tra i processi di gunicorn, nessuna tabella
# aggiuntiva e nessun servizio esterno.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".cache",
        "TIMEOUT": 300,
    }
}

from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}
