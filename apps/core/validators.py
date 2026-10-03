"""Controlli sui file caricati.

Un file caricato non deve poter eseguire codice quando viene aperto dal
gestionale: un HTML o un SVG con dentro uno script, aperto dal browser, potrebbe
usare la sessione di chi lo apre. Per questo i tipi eseguibili si rifiutano già
al caricamento e, in più, i file vengono serviti come scaricamento (vedi
``config/urls.py``).
"""
from pathlib import Path

from django.core.exceptions import ValidationError

# Estensioni che un browser può eseguire (o che si aprono come pagina web).
ESTENSIONI_VIETATE = {
    # pagine web e script
    ".html", ".htm", ".xhtml", ".shtml", ".hta",
    ".svg", ".svgz",
    ".js", ".mjs", ".cjs", ".jsx", ".vbs", ".vbe", ".wsf",
    # eseguibili e comandi
    ".exe", ".msi", ".com", ".scr", ".bat", ".cmd", ".ps1", ".sh", ".jar", ".dll", ".app", ".reg",
    # linguaggi lato server
    ".php", ".phtml", ".asp", ".aspx", ".jsp", ".cgi", ".pl", ".py", ".rb",
}


def valida_file_caricato(file_caricato):
    """Rifiuta i file che il browser potrebbe eseguire."""
    estensione = Path(getattr(file_caricato, "name", "") or "").suffix.lower()
    if estensione in ESTENSIONI_VIETATE:
        raise ValidationError(
            "Questo tipo di file non è ammesso per motivi di sicurezza. "
            "Carica un documento (PDF, immagine, foglio di calcolo…) oppure comprimilo in un file ZIP."
        )
    return file_caricato
