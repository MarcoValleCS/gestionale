"""Contenuti della guida, divisi per area.

Ogni modulo espone ``PAGINE``: una lista di dizionari con slug, titolo, area,
ruoli, ordine, sommario e corpo HTML. L'ordine delle aree nella pagina della
guida è deciso da ``apps.core.guida.ORDINE_AREE``.
"""

from .acquisti import PAGINE as ACQUISTI
from .anagrafiche import PAGINE as ANAGRAFICHE
from .cantieri import PAGINE as CANTIERI
from .collaboratori import PAGINE as COLLABORATORI
from .fatturazione import PAGINE as FATTURAZIONE
from .generale import PAGINE as GENERALI
from .impostazioni import PAGINE as IMPOSTAZIONI
from .magazzino import PAGINE as MAGAZZINO
from .personale import PAGINE as PERSONALE
from .ruoli import PAGINE as PERCORSI
from .vendite import PAGINE as VENDITE

PAGINE = (
    GENERALI
    + PERCORSI
    + ANAGRAFICHE
    + VENDITE
    + ACQUISTI
    + MAGAZZINO
    + CANTIERI
    + FATTURAZIONE
    + PERSONALE
    + COLLABORATORI
    + IMPOSTAZIONI
)

__all__ = ["PAGINE"]
