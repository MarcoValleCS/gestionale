"""Piccolo aiuto per la cache.

Le pagine leggono spesso gli stessi dati (dati azienda, statistiche): tenerli in
cache per qualche decina di secondi alleggerisce molto il carico. Nei test però
la cache non si usa: i test scrivono dati che devono essere riletti subito, e
una copia vecchia farebbe fallire verifiche corrette.
"""
from django.conf import settings
from django.core.cache import cache


def cache_attiva():
    """False durante i test (e se la cache è disattivata a mano)."""
    return not getattr(settings, "IN_TEST", False)


def memoizza(chiave, funzione, timeout=60):
    """Restituisce il valore in cache, altrimenti lo calcola e lo memorizza."""
    if not cache_attiva():
        return funzione()
    return cache.get_or_set(chiave, funzione, timeout)


def dimentica(chiave):
    if cache_attiva():
        cache.delete(chiave)
