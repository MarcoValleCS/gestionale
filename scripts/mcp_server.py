"""MCP del gestionale (trasporto stdio).

Espone i dati del gestionale agli assistenti AI in linguaggio naturale, con
strumenti di lettura (``mcp_read.py``: clienti, preventivi, ordini, DDT,
fatture, magazzino, commesse, lead, personale) e di scrittura (``mcp_write.py``:
creazione e aggiornamento dei documenti). Le scritture riusano i servizi
dell'applicazione, così le regole di business restano in un unico posto.
Le chiamate Django (sincrone) girano in un thread dedicato via
``sync_to_async``. Avvio locale::

    .\\.venv\\Scripts\\python.exe scripts\\mcp_server.py

Per collegarlo a un client MCP (es. Claude Desktop, opencode) puntare il
comando sopra come server stdio.
"""
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


if __name__ == "__main__":
    mcp.run()
