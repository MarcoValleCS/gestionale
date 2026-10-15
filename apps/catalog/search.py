"""Ricerca degli articoli.

Oltre a nome, codice interno e codice a barre si cerca anche fra i codici con
cui i fornitori identificano gli articoli nei loro listini: è il codice che si
ha sotto mano quando si compila un ordine o si legge un'etichetta del
produttore.
"""
from django.db.models import Q


def filtro_codice_fornitore(termine):
    """Filtro Q sugli articoli che hanno quel codice in un listino fornitore.

    Il codice del fornitore sta nella voce di listino: si passa da una
    sottoquery per non ripetere l'articolo quando compare in più listini.
    """
    from apps.purchasing.models import PriceListItem

    return Q(pk__in=PriceListItem.objects.filter(supplier_code__icontains=termine).values("product_id"))


def filtro_articoli(termine):
    """Filtro completo per la ricerca articoli (nome, codici, codice fornitore).

    Ogni parola digitata deve trovare riscontro in almeno uno fra nome,
    codice interno, barcode o codice fornitore: così «sifone 540388» trova
    l'articolo scritto col codice e la descrizione anche in ordine diverso,
    senza dover indovinare il campo giusto.
    """
    filtro = Q()
    for parola in (termine or "").split():
        filtro &= (
            Q(name__icontains=parola)
            | Q(code__icontains=parola)
            | Q(barcode__icontains=parola)
            | filtro_codice_fornitore(parola)
        )
    return filtro
