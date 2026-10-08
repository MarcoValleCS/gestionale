"""Modelli delle email inviate dal gestionale (oggetto e testo modificabili).

I modelli si salvano in ``EmailTemplate``; finché non vengono personalizzati si
usano i testi predefiniti qui sotto.
"""
from .models import EmailTemplate

# Segnaposto disponibili nei modelli (mostrati anche nella pagina delle impostazioni)
SEGNAPOSTO = (
    ("{cliente}", "nome del cliente"),
    ("{numero}", "numero del documento"),
    ("{data}", "data del documento"),
    ("{totale}", "totale del documento"),
    ("{scadenza}", "scadenza di pagamento (fatture)"),
    ("{giorni}", "giorni trascorsi (solleciti)"),
    ("{ritardo}", "ritardo di pagamento (solleciti fattura)"),
    ("{cantiere}", "cantiere collegato"),
    ("{riferimento}", "vostro riferimento"),
    ("{azienda}", "nome dell'azienda"),
    ("{validita}", "riga con la validità (preventivi)"),
    ("{termini}", "condizioni di vendita (riga completa con link, o vuota)"),
)

DEFAULTS = {
    EmailTemplate.KIND_QUOTE: {
        "subject": "Preventivo {numero} – {azienda}",
        "body": (
            "Buongiorno,\n"
            "in allegato il preventivo {numero} del {data} di {totale} €.\n"
            "{validita}"
            "{termini}"
            "Restiamo a disposizione per qualsiasi chiarimento.\n\n"
            "Cordiali saluti\n"
            "{azienda}"
        ),
    },
    EmailTemplate.KIND_INVOICE: {
        "subject": "Fattura {numero} – {azienda}",
        "body": (
            "Buongiorno,\n"
            "in allegato la fattura {numero} del {data} di {totale} €.\n\n"
            "Cordiali saluti\n"
            "{azienda}"
        ),
    },
    EmailTemplate.KIND_QUOTE_REMINDER: {
        "subject": "Preventivo {numero} – siamo a disposizione",
        "body": (
            "Gentile {cliente},\n\n"
            "torniamo sul preventivo {numero} del {data} ({totale} € IVA inclusa), inviato {giorni} giorni fa.\n\n"
            "Restiamo a disposizione per chiarimenti, modifiche o per fissare un appuntamento.\n"
            "Se il preventivo non è più di interesse, ce lo faccia sapere: ci aiuta a non disturbarla.\n\n"
            "Cordiali saluti\n"
            "{azienda}"
        ),
    },
    EmailTemplate.KIND_INVOICE_REMINDER: {
        "subject": "Sollecito fattura {numero}",
        "body": (
            "Gentile {cliente},\n\n"
            "ci risulta ancora da saldare la fattura {numero} del {data}, scaduta il {scadenza}{ritardo}, "
            "di importo {totale} €.\n\n"
            "Se il pagamento è già stato effettuato, la preghiamo di ignorare questo messaggio.\n"
            "Restiamo a disposizione per qualsiasi chiarimento.\n\n"
            "Cordiali saluti\n"
            "{azienda}"
        ),
    },
}


def sostituisci(testo, contesto):
    """Sostituisce i segnaposto senza errori se ne manca qualcuno."""
    for chiave, valore in contesto.items():
        testo = testo.replace("{" + chiave + "}", str(valore if valore is not None else ""))
    return testo


def contenuto(kind, contesto):
    """Oggetto e testo del modello indicato, con i segnaposto sostituiti."""
    modello = EmailTemplate.objects.filter(kind=kind).first()
    default = DEFAULTS.get(kind, {"subject": "", "body": ""})
    oggetto = modello.subject if modello else default["subject"]
    corpo = modello.body if modello else default["body"]
    return sostituisci(oggetto, contesto), sostituisci(corpo, contesto)
