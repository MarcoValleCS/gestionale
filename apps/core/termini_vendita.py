"""Condizioni generali di vendita standard (mobili, arredo bagno, piscine).

Il testo predefinito sta in ``TERMINI_DEFAULT``: copre vendita al dettaglio a
consumatori e professionisti secondo il Codice del consumo (D.lgs 206/2005) e
il Codice civile. È una base standard, non una consulenza legale: prima di
contestazioni importanti farla verificare a un legale.

Il testo usa solo i tag consentiti dal filtro ``richtext`` (b, p, br, ul, li),
così resta identico nella pagina pubblica, nelle stampe e nelle email.
I segnaposto {azienda}, {indirizzo}, {piva}, {email}, {telefono} e {foro}
vengono sostituiti con i dati aziendali al momento dell'uso.
"""

TERMINI_DEFAULT = """<p><b>Condizioni generali di vendita</b></p>
<p><b>1. Oggetto e ambito.</b> Le presenti condizioni disciplinano la vendita di mobili, complementi d'arredo, arredo bagno, piscine, accessori e relativi servizi di installazione da parte di {azienda}, {indirizzo}, P.IVA {piva} (di seguito «Venditore»). Si applicano sia ai consumatori (persone fisiche che acquistano per scopi estranei alla propria attività) sia ai professionisti e alle aziende. Eventuali condizioni difformi del cliente si applicano solo se accettate per iscritto dal Venditore.</p>
<p><b>2. Preventivi.</b> I preventivi sono validi 30 giorni dalla data indicata, salvo diversa indicazione scritta, e non vincolano il Venditore fino alla conferma d'ordine. I prezzi si intendono IVA esclusa, salvo diversa indicazione. Immagini, misure e descrizioni hanno valore indicativo, con le normali tolleranze di produzione.</p>
<p><b>3. Ordini e conclusione del contratto.</b> Il contratto si conclude con l'accettazione scritta del preventivo (firma o conferma via email) e il versamento dell'acconto concordato, di norma pari al 30% salvo diverso accordo; l'acconto vale come caparra confirmatoria (art. 1385 c.c.). Modifiche successive all'ordine possono comportare variazioni di prezzo e di tempi.</p>
<p><b>4. Pagamenti.</b> Saldo prima della consegna o dell'installazione, salvo diverso accordo scritto. Mezzi accettati: bonifico bancario e altri strumenti tracciabili; il contante solo nei limiti di legge. In caso di ritardo, per i professionisti decorrono gli interessi di mora di cui al D.lgs. 231/2002; per i consumatori gli interessi legali. Il mancato pagamento autorizza il Venditore a sospendere consegne e installazioni in corso.</p>
<p><b>5. Consegna.</b> I termini di consegna sono indicativi, salvo termine essenziale pattuito per iscritto. La consegna si intende di norma a piano strada, salvo diverso accordo; facchinaggio ai piani, trasporto in zone disagiate e sosta oltre i tempi concordati possono essere addebitati. Alla consegna il cliente verifica colli e quantità e segnala subito per iscritto sulla bolla eventuali danni o mancanze, pena decadenza.</p>
<p><b>6. Installazione e posa.</b> Se inclusa, l'installazione comprende manodopera e quanto dettagliato in offerta. Predisposizioni murarie, idrauliche ed elettriche, permessi, allacci alle reti e smaltimento di vecchi arredi restano a carico del cliente salvo patto contrario. Il cliente garantisce accessibilità e agibilità del locale alle date concordate.</p>
<p><b>7. Piscine e prodotti su misura.</b> Rilievi e misure vanno confermati dal cliente prima della produzione; mobili su misura e teli/strutture tagliati su misura non possono essere resi. Scavi, riempimenti, idoneità del terreno, autorizzazioni edilizie e paesaggistiche, fornitura e trattamento chimico dell'acqua sono a carico del cliente salvo patto contrario. Le tolleranze tecniche di posa e le lievi differenze cromatiche rispetto a campioni ed esposizione non costituiscono difetto.</p>
<p><b>8. Riserva di proprietà.</b> I beni restano di proprietà del Venditore fino al pagamento integrale del prezzo (art. 1523 c.c.). Il cliente non può rivenderli, darli in garanzia o rimuoverli prima del saldo senza consenso scritto.</p>
<p><b>9. Diritto di recesso del consumatore.</b> Per i contratti conclusi fuori dai locali commerciali o a distanza, il consumatore può recedere entro 14 giorni dalla consegna, con comunicazione scritta a {email}, salvo le esclusioni di legge: in particolare i beni confezionati su misura o personalizzati (art. 59, lett. c, Codice del consumo) non sono restituibili. Il cliente restituisce i beni integri a proprie spese entro 14 giorni dal recesso; il Venditore rimborsa entro 14 giorni quanto incassato, trattenendo l'eventuale diminuzione di valore per uso diverso dalla normale prova.</p>
<p><b>10. Garanzie.</b> Per i consumatori vale la garanzia legale di conformità di 24 mesi dalla consegna (artt. 128-135 Codice del consumo), con denuncia del difetto entro 2 mesi dalla scoperta. Per i professionisti vale la garanzia per vizi ex art. 1490 c.c., con denuncia entro 8 giorni dalla scoperta e azione entro 1 anno dalla consegna. Sono esclusi normale usura, danni da incuria o uso improprio, errato trattamento chimico dell'acqua, installazioni o modifiche eseguite da terzi e materiali di consumo.</p>
<p><b>11. Reclami e assistenza.</b> Reclami e richieste di assistenza vanno inviati a {email} o al {telefono}, indicando numero di documento e descrizione con foto del problema. Il Venditore risponde di norma entro 5 giorni lavorativi.</p>
<p><b>12. Privacy.</b> I dati del cliente sono trattati per eseguire il contratto e gli obblighi di legge, come da informativa privacy fornita al momento dell'ordine.</p>
<p><b>13. Legge applicabile e foro.</b> Si applica la legge italiana. Per i consumatori è competente il foro della loro residenza o domicilio; per gli altri clienti il {foro}.</p>
<p>{azienda} — testo aggiornato a ottobre 2026. Fa fede la versione pubblicata alla pagina termini del sito.</p>"""


def dati_azienda(company):
    """Dati dell'azienda pronti per i segnaposto (stringhe mai None)."""
    pezzi_indirizzo = [p for p in (company.address, company.zip_code, company.city) if p]
    if company.province:
        pezzi_indirizzo.append(f"({company.province})")
    return {
        "azienda": company.name or "",
        "indirizzo": " ".join(pezzi_indirizzo),
        "piva": company.vat_number or "",
        "email": company.email or "",
        "telefono": company.phone or "",
        "foro": f"Foro di {company.city}" if company.city else "Foro competente per territorio",
    }


def render_termini(company, testo=None):
    """Condizioni con i dati aziendali inseriti (testo proprio o standard)."""
    base = testo if testo else TERMINI_DEFAULT
    for chiave, valore in dati_azienda(company).items():
        base = base.replace("{" + chiave + "}", valore)
    return base


def termini_url(company, base_url=""):
    """Indirizzo assoluto della pagina pubblica dei termini (o stringa vuota)."""
    sito = (company.website or "").strip().rstrip("/")
    if base_url:
        return base_url.rstrip("/") + "/termini"
    if not sito:
        return ""
    if not sito.startswith(("http://", "https://")):
        sito = "https://" + sito
    return sito + "/termini"
