"""Guide della fatturazione: DDT, fatture emesse, SDI, acconti/SAL, scadenzario."""

from .base import SOLO_ACQUISTI, SOLO_VENDITE, VENDITE_ACQUISTI, VENDITE_MAGAZZINO

PAGINE = [
    {
        "slug": "ddt",
        "title": "DDT: documenti di trasporto",
        "area": "Fatturazione",
        "roles": VENDITE_MAGAZZINO,
        "order": 10,
        "summary": "Emettere un DDT da un ordine o da zero, scaricare il magazzino e fatturarlo.",
        "body": """
<p>Il DDT accompagna la merce che esce dal magazzino. Non contiene prezzi:
serve a dimostrare cosa è stato consegnato e a chi.</p>

<div class="guida-ruolo">
  <strong>Se sei Magazzino:</strong> puoi creare, modificare, emettere,
  stampare ed eliminare un DDT in bozza. La fattura dal DDT la creano Vendite o
  Amministratore.
</div>

<h3>Emettere un DDT da un ordine</h3>
<ol>
  <li>Apri l'<strong>ordine cliente</strong> confermato.</li>
  <li>Premi <strong>Crea DDT</strong>: il gestionale crea una bozza con le
  quantità ancora da consegnare.</li>
  <li>Controlla cliente, cantiere, destinazione, causale, vettore, colli e peso.</li>
  <li>Salva e poi premi <strong>Emetti e scarica magazzino</strong>.</li>
  <li>Stampa il DDT e fallo firmare alla consegna.</li>
</ol>

<h3>Emettere un DDT da zero</h3>
<ol>
  <li><em>Fatturazione → DDT → Nuovo DDT</em>.</li>
  <li>Scegli cliente, cantiere e dati di trasporto.</li>
  <li>Inserisci le righe: articolo, descrizione, quantità e unità di misura.</li>
  <li>Salva, controlla e premi <strong>Emetti e scarica magazzino</strong>.</li>
</ol>

<h3>Cosa succede all'emissione</h3>
<ul>
  <li>Il DDT passa da <strong>Bozza</strong> a <strong>Emesso</strong>.</li>
  <li>La giacenza degli articoli gestiti a magazzino viene <strong>scaricata</strong>.</li>
  <li>Vengono registrati i movimenti con riferimento al DDT.</li>
  <li>L'ordine collegato aggiorna la quantità consegnata; se è tutto consegnato,
  passa a «Consegnato».</li>
</ul>

<h3>Fatturare il DDT</h3>
<p>Su un DDT emesso e non ancora fatturato compare <strong>Crea fattura da
questo DDT</strong>. La fattura nasce in bozza con le stesse righe. Il DDT viene
segnato come «Fatturato» e non può essere fatturato una seconda volta.</p>
<p>Per raggruppare più consegne in una fattura unica, crea la fattura
manualmente e inserisci le righe, oppure fattura dall'ordine: il gestionale non
unisce automaticamente più DDT.</p>

<h3>Modificare o eliminare</h3>
<ul>
  <li>Un DDT in <strong>bozza</strong> si può modificare o eliminare.</li>
  <li>Un DDT <strong>emesso</strong> non si modifica e non si elimina: ha già
  scaricato il magazzino. Se c'è un errore, la correzione va gestita con un
  documento di reso o una nota di credito, da concordare con l'amministratore.</li>
</ul>

<div class="guida-avviso">Se la merce parte senza DDT, puoi usare «Consegna e
scarica magazzino» dalla scheda dell'ordine. Il DDT resta però la prova di
trasporto più solida: usalo quando serve.</div>
""",
    },
    {
        "slug": "ddt-consultare",
        "title": "DDT: consultare i documenti di trasporto",
        "area": "Fatturazione",
        "roles": SOLO_ACQUISTI,
        "order": 15,
        "summary": "Per Acquisti: leggere un DDT, controllare cosa è stato consegnato e cercare un documento.",
        "body": """
<p>Il ruolo Acquisti può consultare i DDT, ma non crearli, modificarli o
emetterli. La pagina serve a controllare cosa è stato consegnato a un cliente o
a un cantiere.</p>

<h3>Cosa puoi fare</h3>
<ul>
  <li>Aprire l'elenco dei DDT e cercare per numero, cliente o cantiere.</li>
  <li>Leggere le righe, le quantità e i dati di trasporto.</li>
  <li>Stampare il DDT o scaricarlo.</li>
  <li>Vedere se il DDT è in bozza, emesso o già fatturato.</li>
  <li>Aprire l'ordine cliente o la fattura collegata, se il tuo ruolo lo consente.</li>
</ul>

<h3>Cosa non puoi fare</h3>
<ul>
  <li>Creare un nuovo DDT.</li>
  <li>Modificare un DDT in bozza.</li>
  <li>Emettere il DDT e scaricare il magazzino.</li>
  <li>Eliminare un DDT in bozza.</li>
  <li>Creare la fattura dal DDT (è di Vendite o Amministratore).</li>
</ul>

<h3>DDT emesso e fatturato</h3>
<p>Un DDT <strong>emesso</strong> ha già scaricato il magazzino. Se compare anche
il badge <strong>Fatturato</strong>, è già stato collegato a una fattura. Un DDT
in <strong>bozza</strong> non ha ancora scaricato nulla: la merce non è
ufficialmente uscita.</p>

<div class="guida-avviso">Se un DDT non torna con la merce ricevuta o con
l'ordine, segnalalo a Vendite o Magazzino: la correzione va fatta da chi ha
creato il documento, non da Acquisti.</div>
""",
    },
    {
        "slug": "fatture-emesse",
        "title": "Fatture emesse",
        "area": "Fatturazione",
        "roles": SOLO_VENDITE,
        "order": 20,
        "summary": "Emettere, numerare, inviare, incassare e preparare allo SDI una fattura.",
        "body": """
<p>La fattura è il documento fiscale della vendita. Si crea da un DDT, da un
ordine, da un cantiere o manualmente, e nasce sempre in <strong>bozza</strong>.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-fatturazione.svg" alt="Percorsi della fatturazione" loading="lazy">
  <figcaption>Documento, fattura elettronica e cantiere: tre percorsi che si incontrano nella stessa fattura.</figcaption>
</figure>

<h3>Emettere una fattura</h3>
<ol>
  <li>Da un <strong>DDT</strong> emesso: apri il DDT e premi «Crea fattura da questo DDT».</li>
  <li>Da un <strong>ordine</strong>: apri l'ordine e premi «Crea fattura» o «Fattura il resto».</li>
  <li>Da un <strong>cantiere</strong>: usa acconto, SAL o saldo dalla scheda del cantiere.</li>
  <li>Oppure da <em>Fatturazione → Fatture emesse → Nuova fattura</em>, con righe inserite a mano.</li>
  <li>Controlla data, scadenza, condizioni di pagamento e riferimento.</li>
  <li>Salva: il numero viene assegnato automaticamente dalla numerazione.</li>
  <li>Premi <strong>Emetti</strong>: la fattura passa da Bozza a Emessa.</li>
</ol>

<h3>Stati</h3>
<table>
  <thead><tr><th>Stato</th><th>Significato</th></tr></thead>
  <tbody>
    <tr><td>Bozza</td><td>Modificabile ed eliminabile; non entra nello scadenzario.</td></tr>
    <tr><td>Emessa</td><td>Numero assegnato; entra nello scadenzario e può essere inviata.</td></tr>
    <tr><td>Inviata</td><td>L'email è partita (o è stata segnata come inviata).</td></tr>
    <tr><td>Pagata</td><td>L'incasso è stato registrato.</td></tr>
  </tbody>
</table>

<h3>Stampare, PDF e invio email</h3>
<ul>
  <li><strong>Stampa / PDF</strong>: apre la versione stampabile o scarica il PDF generato dal server.</li>
  <li><strong>Invia la fattura</strong>: compila destinatario, oggetto e messaggio;
  il PDF viaggia in allegato. L'invio passa da una coda e parte entro pochi minuti.</li>
  <li>Quando l'email viene spedita, la fattura passa da «Emessa» a «Inviata».</li>
</ul>

<h3>Incassi e solleciti</h3>
<p>La scadenza si calcola dalle condizioni di pagamento. Nello
<a href="/guida/scadenzario/">Scadenzario</a> vedi le fatture aperte e quelle in
ritardo; da lì puoi inviare un sollecito. Quando il cliente paga, apri la
fattura e premi <strong>Segna come pagata</strong>.</p>

<h3>Fattura elettronica</h3>
<p>Dalla scheda della fattura puoi generare l'XML FatturaPA, scaricarlo o
inviarlo allo SDI via PEC. La procedura completa è in
<a href="/guida/fatturazione-elettronica/">Fatturazione elettronica</a>.</p>

<div class="guida-avviso">Una fattura emessa non si modifica e non si elimina
dall'interfaccia. Se hai sbagliato, non creare una seconda fattura: contatta
l'amministratore o il commercialista per la correzione fiscale.</div>
""",
    },
    {
        "slug": "fatturazione-elettronica",
        "title": "Fatturazione elettronica allo SDI",
        "area": "Fatturazione",
        "roles": SOLO_VENDITE,
        "order": 30,
        "summary": "Dati necessari, generazione XML, invio PEC e aggiornamento delle ricevute.",
        "body": """
<p>Il gestionale prepara il file <strong>XML FatturaPA</strong> (formato FPR12),
lo può inviare allo SDI via PEC e registra l'esito sulla fattura. La
conservazione sostitutiva a norma resta fuori: va affidata a un conservatore
accreditato o al commercialista.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-sdi.svg" alt="Flusso della fattura elettronica" loading="lazy">
  <figcaption>Dalla fattura emessa all'XML, alla PEC allo SDI, fino all'esito.</figcaption>
</figure>

<h3>Prima di generare l'XML</h3>
<ul>
  <li><strong>Dati azienda</strong>: P.IVA, codice fiscale, indirizzo completo, regime fiscale e PEC.</li>
  <li><strong>Cliente</strong>: P.IVA o codice fiscale, e codice destinatario SDI (7 caratteri) oppure PEC.</li>
  <li><strong>Righe</strong>: ogni riga deve avere un'aliquota IVA; per le aliquote a 0% serve il codice natura (es. N1, N2.2).</li>
  <li><strong>Fattura emessa</strong>: l'XML si genera solo su una fattura non in bozza.</li>
</ul>
<p>Se manca qualcosa, il gestionale elenca gli errori e non genera il file.</p>

<h3>Generare e scaricare l'XML</h3>
<ol>
  <li>Apri la fattura emessa.</li>
  <li>Nel riquadro <strong>Fattura elettronica (SDI)</strong> premi <strong>Genera XML</strong>.</li>
  <li>Controlla lo stato: diventa «XML generato».</li>
  <li>Premi <strong>Scarica XML</strong> per conservarlo o inviarlo con un altro canale.</li>
</ol>

<h3>Inviare allo SDI</h3>
<ol>
  <li>Controlla che le credenziali <code>EMAIL_*</code> siano configurate: l'invio usa la PEC.</li>
  <li>Premi <strong>Invia allo SDI</strong> e conferma.</li>
  <li>Il gestionale accoda l'email e la trasmette entro pochi minuti.</li>
  <li>Quando arriva la ricevuta sulla casella PEC, torna nella scheda e aggiorna l'esito.</li>
</ol>

<h3>Gli esiti</h3>
<table>
  <thead><tr><th>Esito</th><th>Significato</th></tr></thead>
  <tbody>
    <tr><td>Non inviata</td><td>Nessun XML generato o nessun invio.</td></tr>
    <tr><td>XML generato</td><td>File pronto, non ancora trasmesso.</td></tr>
    <tr><td>Inviata allo SDI</td><td>PEC partita, in attesa di ricevute.</td></tr>
    <tr><td>Consegnata</td><td>Lo SDI ha consegnato la fattura al destinatario.</td></tr>
    <tr><td>Accettata</td><td>La fattura è valida.</td></tr>
    <tr><td>Scartata</td><td>Ci sono errori: correggi e ritrasmetti.</td></tr>
    <tr><td>Mancata consegna</td><td>Il destinatario non ha ricevuto: controlla PEC o codice destinatario.</td></tr>
  </tbody>
</table>
<p>L'esito si aggiorna dalla scheda con il menu «Aggiorna esito» e una nota
facoltativa (es. «scartata: codice destinatario errato»).</p>

<div class="guida-avviso">Il gestionale non legge automaticamente le ricevute
PEC: l'esito va aggiornato a mano. Conserva XML e ricevute secondo le regole
del tuo commercialista.</div>
""",
    },
    {
        "slug": "acconti-sal-saldi",
        "title": "Acconti, SAL e saldo",
        "area": "Fatturazione",
        "roles": SOLO_VENDITE,
        "order": 40,
        "summary": "Fatturare un lavoro a avanzamento: acconto, stato avanzamento lavori e saldo.",
        "body": """
<p>Un lavoro lungo si fattura in più passaggi: <strong>acconto</strong>,
<strong>SAL</strong> (stato avanzamento lavori) e <strong>saldo</strong>. Il
gestionale calcola gli importi sul valore del contratto e tiene conto di quanto
è già stato fatturato, bozze comprese.</p>

<h3>Il valore del contratto</h3>
<p>È la somma degli ordini cliente confermati o consegnati del cantiere. Se non
ci sono ordini, usa la somma dei preventivi accettati. Per questo è importante
collegare ordini e preventivi al cantiere.</p>

<h3>Acconto</h3>
<ol>
  <li>Apri il cantiere e premi <strong>Nuovo acconto</strong>.</li>
  <li>Indica un importo fisso oppure una percentuale del contratto.</li>
  <li>Il gestionale crea una fattura in bozza con una riga «Acconto su contratto».</li>
  <li>Controlla, emetti e invia la fattura.</li>
</ol>

<h3>SAL (avanzamento lavori)</h3>
<ol>
  <li>Premi <strong>Nuovo SAL</strong> e indica la percentuale di avanzamento.</li>
  <li>Il gestionale calcola l'importo obiettivo e sottrae quanto è già stato
  fatturato: emette solo la differenza.</li>
  <li>Il SAL prende un numero progressivo (SAL 1, SAL 2…).</li>
  <li>Se l'avanzamento è già coperto dalle fatture precedenti, il gestionale
  avvisa che non c'è nulla da emettere.</li>
</ol>

<h3>Saldo</h3>
<p>Il pulsante <strong>Saldo</strong> crea una fattura per quanto resta da
fatturare: contratto meno acconti, SAL e altre fatture. Se il residuo è zero,
non crea nulla.</p>

<h3>Acconti su un ordine</h3>
<p>Anche dalla scheda dell'ordine puoi creare un acconto:</p>
<ul>
  <li><strong>Acconto in percentuale</strong>: le righe dell'ordine vengono ridotte alla percentuale scelta.</li>
  <li><strong>Acconto a importo fisso</strong>: una riga «Acconto ordine» che viene
  scalata automaticamente dalle fatture successive, con una riga di storno.</li>
  <li><strong>Fattura il resto</strong>: fattura quanto non è ancora stato fatturato.</li>
</ul>

<h3>Controlli</h3>
<ul>
  <li>La somma di acconti, SAL e saldi non supera il valore del contratto.</li>
  <li>Le bozze contano nel calcolo del residuo: non emettere due volte lo stesso avanzamento.</li>
  <li>Le fatture di acconto, SAL e saldo si collegano al cantiere e compaiono nella sua scheda.</li>
</ul>

<div class="guida-avviso">Prima di emettere un SAL, verifica che il contratto
sia aggiornato: se manca un ordine confermato, il valore del cantiere è più
basso e il SAL risulta sbagliato.</div>
""",
    },
    {
        "slug": "scadenzario",
        "title": "Scadenzario: incassi e pagamenti",
        "area": "Fatturazione",
        "roles": VENDITE_ACQUISTI,
        "order": 50,
        "summary": "Cosa è in scadenza, cosa è in ritardo, come segnare un pagamento e inviare un sollecito.",
        "body": """
<p>Lo scadenzario tiene insieme le fatture da incassare (clienti) e quelle da
pagare (fornitori). È la pagina da guardare ogni settimana per non perdere
scadenze.</p>

<h3>Cosa mostra</h3>
<ul>
  <li><strong>Da incassare</strong>: fatture emesse o inviate non ancora pagate.</li>
  <li><strong>Da pagare</strong>: fatture ricevute registrate e non ancora pagate.</li>
  <li>Per ogni documento: scadenza, cliente o fornitore, numero, importo e giorni di ritardo.</li>
  <li>I totali per fascia: scadute, entro 30 giorni, 31-60, 61-90, oltre 90.</li>
</ul>
<p>Il pulsante <strong>Solo scadute</strong> nasconde tutto ciò che non è in
ritardo. Se una fattura non ha scadenza, il gestionale usa la data del
documento.</p>

<h3>Segnare un incasso o un pagamento</h3>
<ol>
  <li>Apri la fattura dallo scadenzario.</li>
  <li>Premi <strong>Segna come pagata</strong>.</li>
  <li>La fattura esce dallo scadenzario e resta nello storico come «Pagata».</li>
</ol>

<h3>Solleciti</h3>
<p>Dalle righe di incasso scadute puoi premere <strong>Sollecita</strong>: il
gestionale usa il modello email «Sollecito fattura» e allega il PDF. Il
pulsante compare solo se il cliente ha un'email e la fattura è scaduta.</p>
<p>Per i preventivi fermi il sollecito si invia da <a href="/guida/follow-up/">Da seguire</a>.</p>

<h3>Chi vede cosa</h3>
<ul>
  <li><strong>Vendite</strong>: incassi dei clienti.</li>
  <li><strong>Acquisti</strong>: pagamenti ai fornitori.</li>
  <li><strong>Amministratore</strong>: entrambi.</li>
  <li><strong>Magazzino e Personale</strong>: non hanno accesso allo scadenzario.</li>
</ul>

<div class="guida-avviso">Lo scadenzario non genera movimenti bancari: segnare
una fattura come pagata è un'operazione manuale. Confronta sempre con l'estratto
conto prima di chiudere una scadenza.</div>
""",
    },
]
