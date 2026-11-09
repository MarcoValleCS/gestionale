"""WSGI config per il progetto Gestionale."""
import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()


def _preriscalda():
    """Carica subito viste e modelli delle pagine più usate.

    Gunicorn parte con ``--preload``: questo codice gira una volta sola nel
    processo principale, prima di creare i worker, che nascono già pronti
    (e condividono la memoria di quanto caricato qui). Senza, la prima pagina
    dopo ogni riciclo di un worker (``--max-requests``) impiegava 1-2 secondi
    per importare tutte le viste e compilare i modelli di pagina.
    """
    try:
        from django.template.loader import get_template
        from django.urls import get_resolver

        get_resolver().url_patterns  # importa tutti i moduli delle viste
        for nome in ("base.html", "accounts/login.html", "core/dashboard.html"):
            get_template(nome)
    except Exception:  # il preriscaldamento non deve mai impedire l'avvio
        logging.getLogger(__name__).exception("Preriscaldamento non riuscito")
    finally:
        # Nessuna connessione aperta qui deve finire condivisa fra i worker.
        from django.db import connections

        connections.close_all()


_preriscalda()
