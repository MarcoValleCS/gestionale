"""MCP del gestionale: trasporto stdio (locale) oppure HTTP (in produzione).

Espone i dati del gestionale agli assistenti AI in linguaggio naturale, con
strumenti di lettura (``mcp_read.py``: clienti, preventivi, ordini, DDT,
fatture, magazzino, commesse, lead, personale) e di scrittura (``mcp_write.py``:
creazione e aggiornamento dei documenti). Le scritture riusano i servizi
dell'applicazione, così le regole di business restano in un unico posto.
Le chiamate Django (sincrone) girano in un thread dedicato via
``sync_to_async``.

Due modi di usarlo:

**Locale (stdio)** — nessuna porta di rete, il client MCP avvia il processo::

    .\\.venv\\Scripts\\python.exe scripts\\mcp_server.py

**Produzione (HTTP)** — il server ascolta su una porta interna e chiede un
token Bearer a ogni chiamata::

    python scripts/mcp_server.py --trasporto http

In produzione il trasporto HTTP sta dietro Caddy (HTTPS) e dentro Docker: la
porta non è pubblicata, chi arriva al gestionale deve avere il token. Il
token decide anche a chi sono attribuite le scritture (``MCP_USER``).
"""
import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

# L'import registra gli strumenti sull'istanza FastMCP condivisa (mcp_common).
import mcp_read  # noqa: E402, F401
import mcp_write  # noqa: E402, F401
from mcp_common import mcp  # noqa: E402


def _ambiente_attivo(flag: str) -> bool:
    return (os.environ.get(flag) or "").strip().lower() in {"1", "true", "si", "yes"}


def avvia_http(host: str, porta: int) -> None:
    """Avvia il server HTTP (ogni richiesta è autenticata dal token)."""
    import uvicorn

    from mcp_auth import carica_credenziali
    from mcp_http import applicazione_http

    app = applicazione_http()

    print(
        f"MCP in ascolto su http://{host}:{porta}/mcp "
        f"({len(carica_credenziali())} token ammessi).",
        file=sys.stderr,
        flush=True,
    )
    uvicorn.run(
        app,
        host=host,
        port=porta,
        log_level="info",
        proxy_headers=False,
        server_header=False,
    )


def main() -> None:
    analizzatore = argparse.ArgumentParser(description="Server MCP del gestionale.")
    analizzatore.add_argument(
        "--trasporto",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio: server locale senza porte di rete (predefinito). "
        "http: server per la produzione, protetto da token Bearer.",
    )
    analizzatore.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Indirizzo di ascolto del trasporto HTTP (predefinito: solo locale).",
    )
    analizzatore.add_argument(
        "--porta",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8001")),
        help="Porta di ascolto del trasporto HTTP (predefinito: 8001).",
    )
    opzioni = analizzatore.parse_args()

    if opzioni.trasporto == "stdio":
        mcp.run(transport="stdio")
        return

    if not _ambiente_attivo("MCP_ENABLED"):
        raise SystemExit(
            "MCP: il trasporto HTTP è disattivato. Imposta MCP_ENABLED=true nel file .env "
            "per esporre il gestionale agli assistenti AI."
        )
    avvia_http(opzioni.host, opzioni.porta)


if __name__ == "__main__":
    main()
