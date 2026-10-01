"""Formattazione delle note stampabili: HTML limitato a poche decorazioni.

Le note delle condizioni finiscono in un documento che legge il cliente e
vengono rese come HTML: senza un filtro un utente potrebbe inserire script o
immagini esterne. Qui si tiene solo ciò che serve (grassetto, corsivo,
sottolineato, dimensione e allineamento) e si butta via tutto il resto.

Il testo semplice — le note scritte prima che esistesse la formattazione —
passa invariato, con i caratteri < e > correttamente codificati.
"""
import nh3

# Solo decorazioni del testo: niente immagini, link, tabelle o script.
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "br", "p", "div", "span", "ul", "ol", "li"}

# Lo stile è ammesso solo su questi elementi ed è filtrato proprietà per proprietà
ALLOWED_ATTRIBUTES = {
    "span": {"style"},
    "div": {"style"},
    "p": {"style"},
    "li": {"style"},
    "ul": {"style"},
    "ol": {"style"},
}

# Proprietà CSS consentite: niente posizionamento, colori di sfondo o URL
ALLOWED_STYLES = {"font-size", "font-weight", "font-style", "text-decoration", "text-align"}


def clean_notes(value):
    """Ripulisce l'HTML delle note lasciando solo le decorazioni consentite."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        filter_style_properties=ALLOWED_STYLES,
        strip_comments=True,
        link_rel=None,
    )


def is_formatted(value):
    """True se il testo contiene decorazioni HTML (serve solo per i template)."""
    if not value:
        return False
    return any(f"<{tag}" in value for tag in ("b", "i", "u", "strong", "em", "span", "div", "p"))
