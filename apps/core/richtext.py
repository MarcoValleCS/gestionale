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


# ------------------------------------------------------------------ email
# Le email vere sono fatte di tabelle, immagini e stili: la lista bianca delle
# note (solo grassetto e corsivo) le ridurrebbe a testo piatto. Qui si tiene
# molto di più, ma restano fuori script, iframe, form e ogni url pericoloso.

EMAIL_TAGS = {
    "a", "abbr", "address", "article", "aside", "b", "blockquote", "br", "caption", "center",
    "cite", "code", "col", "colgroup", "dd", "del", "details", "div", "dl", "dt", "em",
    "figcaption", "figure", "font", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
    "hr", "i", "img", "ins", "kbd", "li", "main", "mark", "nav", "ol", "p", "pre", "q", "s",
    "samp", "section", "small", "span", "strong", "sub", "summary", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "time", "tr", "u", "ul", "var",
}

# Niente «class»: l'email finisce dentro la pagina del gestionale e potrebbe
# usare le classi di Bootstrap (es. «position-fixed w-100 h-100») per coprire
# la pagina con un finto avviso o un finto modulo di accesso. Le classi
# dell'email stessa non servono: i suoi fogli di stile vengono comunque tolti.
EMAIL_ATTRIBUTES = {
    "*": {"style", "title", "dir", "lang", "align", "valign", "width", "height", "bgcolor"},
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height", "border"},
    "table": {"border", "cellpadding", "cellspacing", "width", "height", "align", "bgcolor", "role"},
    "td": {"colspan", "rowspan", "width", "height", "align", "valign", "bgcolor"},
    "th": {"colspan", "rowspan", "width", "height", "align", "valign", "bgcolor"},
    "tr": {"align", "valign", "bgcolor"},
    "font": {"color", "face", "size"},
    "col": {"width", "span"},
}

# Niente «background» e «list-style» completi: possono contenere url(...) e
# far caricare un indirizzo del gestionale (o esterno) all'apertura dell'email.
EMAIL_STYLES = {
    "color", "background-color", "font", "font-family", "font-size", "font-weight",
    "font-style", "font-variant", "text-decoration", "text-align", "text-transform",
    "vertical-align", "line-height", "letter-spacing", "word-break", "overflow-wrap", "white-space",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-color", "border-style", "border-width", "border-collapse", "border-spacing", "border-radius",
    "width", "max-width", "min-width", "height", "max-height", "min-height", "display",
    "float", "clear", "list-style-type", "table-layout",
}

EMAIL_URL_SCHEMES = {"http", "https", "mailto", "tel", "data", "cid"}

# Collegamenti e immagini ammessi così come sono: solo indirizzi completi.
EMAIL_SCHEMI_ESTERNI = ("http:", "https:", "mailto:", "tel:")

# Pezzi di CSS che fanno caricare qualcosa: uno stile che li contiene si toglie
# tutto (la barra rovesciata copre le sequenze di escape come «u\72l(»).
EMAIL_STILI_VIETATI = ("url", "image", "expression", "\\")


def clean_email_html(value, mappa_allegati=None):
    """Ripulisce l'HTML di un'email mantenendone la grafica.

    ``mappa_allegati`` collega gli identificativi delle immagini incorporate
    (``cid:...``) all'indirizzo da cui scaricarle dal gestionale: così i loghi e
    le immagini dentro il messaggio si vedono.
    """
    if not value:
        return ""
    mappa = {str(chiave).strip().strip("<>").lower(): url for chiave, url in (mappa_allegati or {}).items()}

    def filtra_attributo(tag, attributo, valore):
        if attributo == "style":
            minuscolo = (valore or "").lower()
            return None if any(pezzo in minuscolo for pezzo in EMAIL_STILI_VIETATI) else valore
        if attributo not in ("src", "href"):
            return valore
        minuscolo = (valore or "").strip().lower()
        if minuscolo.startswith("cid:"):
            chiave = valore.strip()[4:].strip().strip("<>").lower()
            return mappa.get(chiave)  # None = attributo rimosso
        # I link «data:» possono contenere HTML/script: si lascia il «data:» solo
        # per le immagini incorporate (img src), non per i collegamenti.
        if minuscolo.startswith("data:"):
            return valore if (tag == "img" and attributo == "src") else None
        if minuscolo.startswith(EMAIL_SCHEMI_ESTERNI):
            return valore
        # Indirizzi relativi («/vendite/ordini/5/consegna/», «//host», «#…»):
        # dentro il gestionale punterebbero alle sue pagine con la sessione di
        # chi legge l'email. Un'immagine così basterebbe a far partire una
        # richiesta appena si apre il messaggio: si tolgono.
        return None

    return nh3.clean(
        value,
        tags=EMAIL_TAGS,
        attributes=EMAIL_ATTRIBUTES,
        attribute_filter=filtra_attributo,
        filter_style_properties=EMAIL_STYLES,
        url_schemes=EMAIL_URL_SCHEMES,
        strip_comments=True,
        link_rel="noopener noreferrer",
    )
