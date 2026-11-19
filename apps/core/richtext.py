"""Formattazione delle note stampabili: HTML limitato a poche decorazioni.

Le note delle condizioni finiscono in un documento che legge il cliente e
vengono rese come HTML: senza un filtro un utente potrebbe inserire script o
immagini esterne. Qui si tiene solo ciò che serve (grassetto, corsivo,
sottolineato, dimensione e allineamento) e si butta via tutto il resto.

Il testo semplice — le note scritte prima che esistesse la formattazione —
passa invariato, con i caratteri < e > correttamente codificati.
"""
import nh3

# Solo decorazioni del testo e collegamenti http(s): niente immagini, tabelle o script.
# I link servono, ad esempio, per rimandare alle condizioni di vendita
# pubblicate sul sito (anche nel PDF i link restano cliccabili).
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "br", "p", "div", "span", "ul", "ol", "li", "a"}

# Lo stile è ammesso solo su questi elementi ed è filtrato proprietà per proprietà
ALLOWED_ATTRIBUTES = {
    "span": {"style"},
    "div": {"style"},
    "p": {"style"},
    "li": {"style"},
    "ul": {"style"},
    "ol": {"style"},
    "a": {"href", "title"},
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
        url_schemes={"http", "https"},
        strip_comments=True,
        link_rel="noopener",
    )


def is_formatted(value):
    """True se il testo contiene decorazioni HTML (serve solo per i template)."""
    if not value:
        return False
    return any(f"<{tag}" in value for tag in ("b", "i", "u", "strong", "em", "span", "div", "p"))


# ------------------------------------------------------------------- guida
# La guida del gestionale è scritta da chi amministra il programma: servono
# titoli, elenchi, link e tabelle, ma non script né immagini esterne.

GUIDA_TAGS = {
    "h2", "h3", "h4", "p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
    "a", "code", "pre", "blockquote", "div", "span", "small", "hr",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    # Immagini e didascalie: solo file locali sotto static/img/guida/.
    "img", "figure", "figcaption",
}

GUIDA_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "figure": {"class"},
    "figcaption": {"class"},
    "*": {"class"},
}

GUIDA_URL_SCHEMES = {"http", "https", "mailto"}
GUIDA_IMMAGINI = "/static/img/guida/"


def _filtra_attributo_guida(tag, attributo, valore):
    """Consente solo le immagini della guida, mai quelle esterne."""
    if tag == "img" and attributo == "src":
        percorso = (valore or "").strip()
        if not percorso.startswith(GUIDA_IMMAGINI):
            return None
    return valore


def clean_guida(value):
    """Ripulisce l'HTML di una pagina della guida."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=GUIDA_TAGS,
        attributes=GUIDA_ATTRIBUTES,
        attribute_filter=_filtra_attributo_guida,
        url_schemes=GUIDA_URL_SCHEMES,
        strip_comments=True,
        link_rel="noopener noreferrer",
    )
