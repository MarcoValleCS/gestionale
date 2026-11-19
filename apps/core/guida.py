"""Contenuti della guida del gestionale.

Ogni pagina dichiara i ruoli che possono leggerla: chi entra trova solo le
istruzioni delle funzioni che può davvero usare. I testi si caricano con
``python manage.py carica_guida`` e poi si possono modificare dal gestionale
(Impostazioni → Guida, oppure dal pulsante «Modifica» in ogni pagina).

Il testo è HTML: titoli, elenchi, tabelle, immagini locali della guida. Tutto
il resto viene rimosso al salvataggio.
"""

from .guida_contenuti import PAGINE

# Ordine con cui le sezioni compaiono nella pagina della guida. Le aree non
# elencate finiscono in fondo, in ordine alfabetico.
ORDINE_AREE = [
    "Generale",
    "Percorsi per ruolo",
    "Anagrafiche",
    "Vendite",
    "Acquisti",
    "Magazzino",
    "Cantieri",
    "Fatturazione",
    "Personale",
    "Collaboratori",
    "Impostazioni",
]

# Pagine tolte dal programma: ``carica_guida`` le cancella (o, se modificate a
# mano, le nasconde), così non restano istruzioni su funzioni che non esistono.
PAGINE_RITIRATE = ("posta",)

__all__ = ["PAGINE", "ORDINE_AREE", "PAGINE_RITIRATE"]
