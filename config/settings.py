"""Configurazione del progetto Gestionale.

Le variabili d'ambiente permettono di usare la stessa codebase in sviluppo
(SQLite, debug attivo) e in produzione su VPS Linux (PostgreSQL, HTTPS).
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# True quando si stanno eseguendo i test: alcune ottimizzazioni (cache, nomi dei
# file statici) si disattivano, così i test non dipendono da dati raccolti prima.
IN_TEST = "test" in sys.argv


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- Sicurezza
SECRET_KEY = env("DJANGO_SECRET_KEY", "chiave-di-sviluppo-non-utilizzare-in-produzione")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Gli healthcheck interni di Docker chiamano http://127.0.0.1:8000: si aggiungono
# sempre localhost e 127.0.0.1 (in coda), senza togliere i domini pubblici.
for _host_interno in ("localhost", "127.0.0.1"):
    if _host_interno not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host_interno)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

if env_bool("DJANGO_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    # Difesa in profondità: Caddy redirige già HTTP→HTTPS, ma così lo fa anche
    # Django se una richiesta arrivasse in chiaro (es. da un altro proxy).
    SECURE_SSL_REDIRECT = True

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

# Indirizzo che riceve gli avvisi automatici (backup fallito, sito irraggiungibile,
# disco quasi pieno). Se vuoto si usa l'email dell'azienda.
AVVISO_EMAIL = env("AVVISO_EMAIL", "")



# ------------------------------------------------- Posta in arrivo (IMAP)

# Serve a leggere la casella aziendale dal gestionale. Se non indicate, si

# usano le stesse credenziali dell'invio.

IMAP_HOST = env("IMAP_HOST", "imaps.aruba.it")

IMAP_PORT = int(env("IMAP_PORT", "993"))

IMAP_USER = env("IMAP_USER", EMAIL_HOST_USER)

IMAP_PASSWORD = env("IMAP_PASSWORD", EMAIL_HOST_PASSWORD)

IMAP_FOLDER = env("IMAP_FOLDER", "INBOX")

IMAP_IS_CONFIGURED = bool(IMAP_HOST and IMAP_USER and IMAP_PASSWORD)



# Domini considerati "di casa": le email che arrivano da qui sono sempre

# mostrate (colleghi, PEC, SDI). Si ricavano dall'indirizzo di invio, oppure

# si indicano a mano in DOMINI_INTERNI (separati da virgola).

def _dominio_di(indirizzo):

    return indirizzo.split("@")[-1].strip().lower() if "@" in indirizzo else ""





_domini_automatici = {d for d in (_dominio_di(EMAIL_HOST_USER), _dominio_di(DEFAULT_FROM_EMAIL)) if d}

DOMINI_INTERNI = {d.strip().lower() for d in env("DOMINI_INTERNI", "").split(",") if d.strip()} or _domini_automatici



# Mittenti che non vanno mai persi: il Sistema di Interscambio (fatture

# elettroniche) e le PEC. Si possono aggiungere altri indirizzi, separati da

# virgola, in MITTENTI_IMPORTANTI.

MITTENTI_IMPORTANTI = {m.strip().lower() for m in env("MITTENTI_IMPORTANTI", "sdi01@pec.fatturapa.it").split(",") if m.strip()}
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
    "apps.leads",
    "apps.gallery",
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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
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

# Cartella dei backup notturni (in produzione il contenitore la vede in sola
# lettura: si possono scaricare dal gestionale, così se ne tiene una copia
# anche fuori dal server).
BACKUP_ROOT = Path(env("BACKUP_ROOT", str(BASE_DIR / "backups")))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # I file statici portano nel nome un'impronta del contenuto: quando
    # cambiano, cambia l'indirizzo, quindi il browser può tenerli in cache a
    # lungo senza rischiare di mostrare una versione vecchia.
    # Nei test si usano i nomi normali: la mappa delle impronte richiede di
    # avere raccolto i file, cosa che nei test non serve.
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if IN_TEST
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- Log
# Cosa finisce nei log e cosa no:
#  - le password non vengono mai registrate (gli accessi sono richieste POST e
#    il corpo non viene mai stampato);
#  - le credenziali di posta stanno solo nel file .env;
#  - i 404 non vengono registrati: l'indirizzo potrebbe contenere il testo di
#    una ricerca (nome di un cliente), che non serve tenere nei log;
#  - gli errori gravi restano registrati per poterli capire.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "semplice": {"format": "{levelname} {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "semplice"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # Solo gli errori veri, non ogni pagina non trovata
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# -------------------------------------------------------------- Cache
# Cache su file: condivisa tra i processi di gunicorn, nessuna tabella
# aggiuntiva e nessun servizio esterno. La usa anche il limitatore anti-abuso.
# Durante i test le ottimizzazioni si disattivano (vedi apps.core.cache): i test
# scrivono dati che devono essere riletti subito.
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
