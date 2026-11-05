"""Guide delle vendite: lead, preventivi, ordini, follow-up, statistiche, provvigioni."""

from .base import COMMERCIALE, SOLO_VENDITE

PAGINE = [
    {
        "slug": "lead",
        "title": "Lead: la pipeline commerciale",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 5,
        "summary": "Registrare una trattativa, spostarla fra le fasi e trasformarla in preventivo.",
        "body": """
<p>Un <strong>lead</strong> è una trattativa non ancora definita: una richiesta
arrivata dal sito, una telefonata, un contatto conosciuto a una fiera. La
bacheca mostra i lead divisi per fase, come una pipeline commerciale.</p>

<h3>La bacheca</h3>
<ul>
  <li>Ogni colonna è una <strong>fase</strong> (es. Nuovo, Contattato, Preventivo mandato, Trattativa, Vinto, Perso).</li>
  <li>La ricerca filtra per nome, contatto, telefono e città; la spunta <strong>Solo i miei</strong> mostra i lead di cui sei responsabile.</li>
  <li>In alto vedi il numero di lead aperti, il valore stimato e quanti sono in ritardo rispetto alla prossima azione.</li>
  <li>Il menu a tendina sulla scheda sposta il lead in un'altra fase.</li>
</ul>

<h3>Creare un lead</h3>
<ol>
  <li>Premi <strong>Nuovo lead</strong>.</li>
  <li>Indica un riferimento chiaro (es. «Rossi - piscina via Verdi»), il contatto se esiste, telefono, email e città.</li>
  <li>Compila la <strong>fonte</strong> (sito, telefono, passaparola…), la <strong>fase</strong>, il <strong>responsabile</strong> e il <strong>valore stimato</strong>.</li>
  <li>Indica la <strong>prossima azione</strong>: è la data che il gestionale evidenzia in rosso quando scade.</li>
  <li>Salva. Il lead compare nella colonna della sua fase.</li>
</ol>

<h3>Dalla trattativa al preventivo</h3>
<ol>
  <li>Apri il lead e premi <strong>Crea preventivo</strong>.</li>
  <li>Il gestionale crea il preventivo in bozza; se il lead non ha una scheda contatto, la crea con i dati disponibili.</li>
  <li>Il lead passa automaticamente alla fase configurata come «preventivo creato» (di norma «Preventivo mandato»).</li>
  <li>Compila le righe del preventivo e invialo al cliente.</li>
</ol>

<h3>Chiudere un lead</h3>
<p>Quando il lavoro è vinto, sposta il lead in una fase con esito «Vinto»;
quando è perso, in una fase «Perso». Le fasi e i loro esiti si configurano da
<em>Impostazioni → Fasi lead</em> (solo amministratore). Il lead non si elimina
automaticamente: puoi cancellarlo con il cestino, ma è meglio conservarlo per
le statistiche.</p>

<h3>Lead dal sito web</h3>
<p>Il modulo contatti del sito può inviare i lead al gestionale tramite
l'endpoint <code>/lead/da-sito/</code>, protetto da un token condiviso. I lead
arrivano nella fase iniziale e con un pallino rosso nel menu finché non vengono
aperti. La configurazione è a carico dell'amministratore.</p>

<div class="guida-avviso">Il valore stimato è un'informazione commerciale, non
un importo fatturabile: non entra nelle statistiche del fatturato. Il fatturato
si calcola sugli ordini consegnati.</div>
""",
    },
    {
        "slug": "preventivi",
        "title": "Preventivi",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 10,
        "summary": "Preparare, stampare, inviare, duplicare e far diventare ordine un preventivo.",
        "body": """
<p>Il preventivo è il documento con cui si propone un lavoro al cliente. Nasce
in <strong>bozza</strong>, si invia, si accetta o si rifiuta, e da quello
accettato si crea l'<strong>ordine cliente</strong>.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/ciclo-preventivo.svg" alt="Ciclo di vita del preventivo" loading="lazy">
  <figcaption>Gli stati del preventivo: bozza, inviato, accettato, convertito in ordine; oppure rifiutato o scaduto.</figcaption>
</figure>

<h3>Creare un preventivo</h3>
<ol>
  <li><strong>Vendite → Preventivi → Nuovo preventivo</strong>.</li>
  <li>Scegli il <strong>cliente</strong> (o crealo al volo), il <strong>cantiere</strong> se serve, la data e la validità.</li>
  <li>Compila le righe: nella colonna <em>Articolo</em> scrivi qualche lettera del
  nome o il codice (anche quello del fornitore) e scegli dalla tendina.
  Descrizione, quantità, prezzo e IVA si compilano da soli; puoi correggerli.</li>
  <li>Usa il tipo riga <strong>Sezione</strong> per raggruppare per ambiente (es.
  «Bagno 1») e <strong>Sottosezione</strong> per un secondo livello. Le righe
  <strong>Nota</strong> non entrano nei totali.</li>
  <li>Sposta le righe con le frecce su/giù: l'ordine viene salvato.</li>
  <li>Salva: i totali vengono ricalcolati dal server.</li>
</ol>

<h3>Sconti, IVA e margine</h3>
<p>Ogni riga può avere uno sconto percentuale e un'aliquota IVA. Il riquadro
<strong>Totali</strong> mostra imponibile, IVA per aliquota e totale. Sotto c'è
il <strong>Margine</strong>: costo merce, eventuale provvigione, margine e
marginalità. Il costo viene dall'anagrafica dell'articolo o dal listino del
fornitore: è un'indicazione, non un dato contabile.</p>

<h3>Modelli di preventivo</h3>
<p>Se ci sono righe che usi spesso, salva un <strong>modello</strong> da
<em>Vendite → Modelli preventivo</em>. Nel modulo del preventivo scegli il
modello dall'elenco e le righe si compilano da sole. La guida è in
<a href="/guida/modelli-preventivo/">Modelli di preventivo</a>.</p>

<h3>Stampare, scaricare il PDF o inviare</h3>
<ul>
  <li><strong>Stampa</strong>: apre la versione da stampare o salvare in PDF dal browser.</li>
  <li><strong>PDF</strong>: scarica il PDF generato dal gestionale, con logo e colori aziendali.</li>
  <li><strong>Invia email</strong>: compila destinatario, oggetto e messaggio; il
  preventivo viaggia in allegato PDF. L'invio passa da una coda e parte entro
  pochi minuti. Quando l'email viene spedita, il preventivo passa da «Bozza» a
  «Inviato».</li>
</ul>

<h3>Accettare, rifiutare, convertire</h3>
<ul>
  <li><strong>Accettato dal cliente</strong>: porta il preventivo in stato «Accettato».</li>
  <li><strong>Rifiutato</strong>: chiude la trattativa come persa.</li>
  <li><strong>Crea ordine cliente</strong>: disponibile sui preventivi accettati;
  copia righe, prezzi, condizioni e provvigione nell'ordine.</li>
  <li><strong>Duplica</strong>: crea una copia in bozza, utile per un preventivo simile.</li>
</ul>

<h3>Modificare o eliminare</h3>
<p>Solo i preventivi in <strong>bozza</strong> o <strong>inviati</strong> si
possono modificare. Un preventivo convertito in ordine non si può eliminare: è
lo storico del lavoro. Se hai sbagliato qualcosa, duplicalo e correggi la copia.</p>

<div class="guida-avviso">La validità del preventivo è la data oltre la quale
il documento è considerato scaduto. Il gestionale la evidenzia in giallo e la
usa in «Da seguire» per i solleciti.</div>
""",
    },
    {
        "slug": "modelli-preventivo",
        "title": "Modelli di preventivo",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 20,
        "summary": "Salvare le righe ricorrenti e caricarle in un nuovo preventivo con un clic.",
        "body": """
<p>Un <strong>modello di preventivo</strong> è un preventivo senza cliente:
contiene righe, condizioni e note che usi spesso (es. «Kit bagno tipo»,
«Apertura piscina», «Manutenzione annuale»).</p>

<h3>Creare un modello</h3>
<ol>
  <li>Apri <em>Vendite → Modelli preventivo → Nuovo modello</em>.</li>
  <li>Indica nome, descrizione, condizione di pagamento, condizioni stampate e note.</li>
  <li>Compila le righe come in un preventivo: articoli, quantità, prezzi, sconti e IVA.</li>
  <li>Imposta l'ordine di visualizzazione e salva.</li>
</ol>

<h3>Usare un modello</h3>
<ol>
  <li>Crea un nuovo preventivo.</li>
  <li>Nel riquadro <strong>Modello</strong> scegli il modello dall'elenco.</li>
  <li>Le righe e le condizioni vengono caricate nel documento; puoi modificarle
  prima di salvare.</li>
</ol>

<h3>Modificare o eliminare</h3>
<p>Puoi modificare un modello in qualsiasi momento: i preventivi già creati non
cambiano. L'eliminazione non tocca i documenti esistenti.</p>

<div class="guida-suggerimento">Tieni i modelli pochi e chiari: un modello per
ogni lavoro ricorrente, non un modello per ogni cliente. Per le varianti usa le
righe del preventivo, non nuovi modelli.</div>
""",
    },
    {
        "slug": "ordini-cliente",
        "title": "Ordini cliente",
        "area": "Vendite",
        "roles": COMMERCIALE,
        "order": 30,
        "summary": "Confermare l'ordine, generare il riordino, consegnare e fatturare.",
        "body": """
<p>L'ordine cliente è la conferma di un lavoro. Nasce da un preventivo
accettato o da zero, e da qui partono gli impegni di magazzino, gli ordini
fornitore, i DDT e le fatture.</p>

<div class="guida-ruolo">
  <strong>Se sei Magazzino:</strong> puoi consultare l'ordine, creare il DDT e
  registrare la consegna. Non puoi creare, modificare, confermare, annullare o
  fatturare l'ordine.<br>
  <strong>Se sei Acquisti:</strong> puoi consultare l'ordine e gli ordini
  fornitore collegati, ma non modificarlo.
</div>

<h3>Creare un ordine</h3>
<ol>
  <li>Puoi partire da un <strong>preventivo</strong> (scheda → «Crea ordine cliente») oppure da <em>Vendite → Ordini cliente → Nuovo ordine</em>.</li>
  <li>Compila le righe come nel preventivo: articolo, quantità, prezzo, sconto, IVA.</li>
  <li>Salva: l'ordine resta in <strong>bozza</strong> finché non lo confermi.</li>
</ol>

<h3>Confermare l'ordine e il riordino automatico</h3>
<p>Premendo <strong>Conferma ordine</strong> il gestionale controlla la
giacenza di ogni articolo e genera gli <strong>ordini fornitore</strong> per
quanto manca. Con il pulsante <strong>e riordina scorte</strong> vengono
aggiunti al riordino anche gli articoli sotto scorta minima con fornitore
abituale, per riportarli almeno alla scorta.</p>
<p>Gli articoli senza fornitore abituale vengono elencati a parte: va indicato
il fornitore nella scheda dell'articolo perché il riordino li includa.</p>
<p>La guida dettagliata è in <a href="/guida/riordino-automatico/">Riordino automatico</a>.</p>

<h3>Modificare un ordine</h3>
<p>Un ordine in bozza o confermato si può modificare. Se è già confermato, il
gestionale mostra un avviso: cambiare quantità o prezzi dopo la conferma può
rendere diversi i conti rispetto agli ordini fornitore già generati. Un ordine
consegnato o annullato non è più modificabile.</p>

<h3>Consegnare</h3>
<ul>
  <li>Dal menu <strong>DDT</strong>: apri l'ordine e premi «Crea DDT», poi emetti il documento. Il DDT scarica il magazzino.</li>
  <li>Dalla scheda dell'ordine: <strong>Consegna e scarica magazzino</strong> registra la consegna e scarica le quantità.</li>
  <li>Se la merce è già stata ricevuta dal fornitore, la colonna <strong>Ricevuta</strong> mostra quanto è arrivato e non ancora consegnato.</li>
</ul>

<h3>Annullare o eliminare</h3>
<ul>
  <li><strong>Annulla</strong>: disponibile su un ordine confermato, purché nessuna riga sia già stata consegnata.</li>
  <li><strong>Elimina</strong>: solo per gli ordini in bozza.</li>
</ul>

<h3>Fatturare</h3>
<p>Dalla scheda dell'ordine puoi creare la fattura, anche parziale:
<strong>Acconto</strong> (percentuale o importo fisso), <strong>Fattura il
resto</strong> o fattura completa. La guida è in
<a href="/guida/acconti-sal-saldi/">Acconti, SAL e saldo</a>.</p>

<div class="guida-avviso">Il fatturato delle statistiche si calcola sugli ordini
<strong>consegnati</strong>: finché l'ordine è confermato, non entra nei
numeri.</div>
""",
    },
    {
        "slug": "riordino-automatico",
        "title": "Riordino automatico: come nascono gli ordini fornitore",
        "area": "Vendite",
        "roles": COMMERCIALE,
        "order": 40,
        "summary": "Cosa succede alla conferma di un ordine, come si calcolano le carenze e cosa fare senza fornitore.",
        "body": """
<p>Il riordino automatico evita di scoprire a consegna che manca la merce. Alla
conferma di un ordine cliente il gestionale confronta la giacenza con le
quantità richieste e crea gli ordini fornitore per le differenze.</p>

<h3>Il calcolo, passo per passo</h3>
<ol>
  <li>Per ogni riga dell'ordine prende la quantità <strong>ancora da consegnare</strong> (totale meno già consegnato).</li>
  <li>Somma le quantità dello stesso articolo se compare in più righe.</li>
  <li>Confronta con la <strong>giacenza totale</strong> dell'articolo (somma di tutti i magazzini).</li>
  <li>Se la giacenza non basta, la differenza diventa la quantità da ordinare.</li>
  <li>Raggruppa le carenze per <strong>fornitore abituale</strong> e crea un ordine fornitore per fornitore.</li>
  <li>Usa il prezzo di acquisto del listino attivo, se c'è; altrimenti il prezzo di acquisto dell'articolo.</li>
  <li>Calcola la consegna prevista sommando i giorni di consegna del fornitore.</li>
  <li>Scrive una nota sull'ordine fornitore con il numero dell'ordine cliente di origine.</li>
</ol>

<h3>Il pulsante «e riordina scorte»</h3>
<p>Oltre alle carenze dell'ordine, riordina anche gli articoli sotto scorta
minima con fornitore abituale. Per ognuno ordina la quantità necessaria a
tornare alla scorta minima. È utile all'inizio della stagione o dopo un periodo
di vendite intense.</p>

<h3>Articoli senza fornitore</h3>
<p>Se un articolo non ha un <strong>fornitore abituale</strong>, il gestionale
non può creare l'ordine. Mostra un avviso con l'articolo e la quantità mancante:
apri la scheda articolo, imposta il fornitore e crea l'ordine fornitore a mano,
oppure riprova la conferma su un nuovo ordine.</p>

<h3>Cosa non viene ordinato</h3>
<ul>
  <li>Articoli <strong>non gestiti a magazzino</strong> (servizi, manodopera, trasporti).</li>
  <li>Kit: non hanno giacenza, si ordinano i componenti.</li>
  <li>Righe di testo (sezioni, sottosezioni, note).</li>
  <li>Articoli con giacenza sufficiente.</li>
</ul>

<h3>Dopo la generazione</h3>
<p>Gli ordini fornitore sono in <strong>bozza</strong>: controllali, eventualmente
aggiungi righe, inviali al fornitore o all'agenzia. Quando arriva la merce,
ricevila dall'ordine fornitore: il magazzino si carica e l'ordine cliente mostra
la quantità ricevuta.</p>

<div class="guida-avviso">La conferma non impegna la giacenza: due ordini
confermati quasi insieme possono generare ordini fornitore per la stessa merce.
Controlla sempre gli ordini generati prima di inviarli al fornitore.</div>
""",
    },
    {
        "slug": "follow-up",
        "title": "Preventivi da seguire e solleciti",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 50,
        "summary": "Trovare i preventivi fermi, misurare la conversione e inviare un sollecito.",
        "body": """
<p>La pagina <strong>Da seguire</strong> raccoglie i preventivi in bozza o
inviati che non hanno ancora una risposta. Serve a non lasciare indietro le
trattative.</p>

<h3>Cosa mostra</h3>
<ul>
  <li><strong>Valore in attesa</strong>: somma dei preventivi fermi da almeno il numero di giorni scelto.</li>
  <li><strong>Tasso di conversione</strong>: preventivi convertiti diviso preventivi decisi (convertiti + rifiutati).</li>
  <li><strong>Tempo medio di chiusura</strong>: giorni medi dalla data del preventivo all'ordine.</li>
  <li><strong>Preventivi inviati</strong>: conteggio e quanti sono da sollecitare.</li>
</ul>

<h3>Filtrare per giorni</h3>
<p>Il menu «Fermi da almeno» sceglie 3, 7, 14 o 30 giorni. La tabella mostra
data, giorni di attesa, validità e valore. Un preventivo scaduto è evidenziato
in rosso.</p>

<h3>Inviare un sollecito</h3>
<ol>
  <li>Nella riga del preventivo premi <strong>Sollecita</strong>.</li>
  <li>Il gestionale usa il modello email «Sollecito preventivo» e allega il PDF.</li>
  <li>L'email viene accodata e parte entro pochi minuti.</li>
</ol>
<p>Se il cliente non ha un'email, il pulsante non compare: aggiorna la scheda
contatto o contattalo per telefono.</p>

<h3>Chiudere la trattativa</h3>
<p>Quando il cliente risponde, apri il preventivo e scegli
<strong>Accettato dal cliente</strong> o <strong>Rifiutato</strong>. Se accetta,
crea l'ordine cliente. Così il preventivo esce dall'elenco «Da seguire» e le
statistiche di conversione restano corrette.</p>

<div class="guida-avviso">Il tasso di conversione considera solo i preventivi
decisi: quelli ancora aperti non abbassano il risultato. Se vedi un valore
strano, controlla che i preventivi chiusi siano stati segnati come accettati o
rifiutati.</div>
""",
    },
    {
        "slug": "statistiche-vendite",
        "title": "Statistiche ed export Excel",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 60,
        "summary": "Fatturato, margine e classifiche per articolo, fornitore, cliente e cantiere.",
        "body": """
<p>La pagina <strong>Statistiche</strong> legge gli <strong>ordini cliente
consegnati</strong> e calcola fatturato, costo del venduto, provvigioni, margine
e marginalità. Non è una contabilità ufficiale: è uno strumento per capire dove
si guadagna.</p>

<h3>Il periodo</h3>
<p>Il menu <strong>Periodo</strong> sceglie mese corrente, anno corrente o ultimi
12 mesi. Il grafico mostra fatturato e margine mese per mese; i pulsanti
<code>1</code>, <code>3</code>, <code>6</code>, <code>12</code> cambiano
l'ampiezza e le frecce spostano la finestra indietro.</p>

<h3>Le classifiche</h3>
<ul>
  <li><strong>Marginalità per articolo</strong>: quantità, fatturato, costo, margine e percentuale.</li>
  <li><strong>Marginalità per fornitore</strong>: quanto rende la merce di ciascun fornitore.</li>
  <li><strong>Fatturato per cliente</strong>: chi porta più margine.</li>
  <li><strong>Fatturato per cantiere</strong>: solo gli ordini collegati a un cantiere.</li>
</ul>

<h3>Come si calcola il margine</h3>
<p>Il costo di ogni riga usa il <strong>costo unitario fissato alla conferma
dell'ordine</strong>; se manca, usa il prezzo di acquisto attuale dell'articolo.
La provvigione viene ripartita sulle righe in proporzione al loro valore e
sottratta dal margine. Il margine può quindi essere diverso dal semplice
«prezzo meno ultimo costo».</p>

<h3>Esportare in Excel</h3>
<p>Il pulsante <strong>Esporta Excel</strong> scarica una riga per articolo
venduto, con data, documento, cliente, venditore, codice, descrizione,
quantità, unità, prezzo, sconto, imponibile, costo, provvigione, margine e
margine percentuale. Il file si apre con Excel o LibreOffice.</p>

<div class="guida-avviso">Se un ordine non è segnato come consegnato, non entra
nelle statistiche. Se i numeri sembrano bassi, controlla gli ordini confermati
ma non ancora consegnati.</div>
""",
    },
    {
        "slug": "provvigioni",
        "title": "Provvigioni",
        "area": "Vendite",
        "roles": SOLO_VENDITE,
        "order": 70,
        "summary": "Impostare agente e percentuale, calcolare le provvigioni maturate e da liquidare.",
        "body": """
<p>La provvigione è la quota riconosciuta a chi ha presentato il cliente. Si
imposta sul <strong>preventivo</strong> o sull'<strong>ordine</strong>, indicando
beneficiario e percentuale.</p>

<h3>Impostare una provvigione</h3>
<ol>
  <li>Apri il preventivo o l'ordine in modifica.</li>
  <li>Nel riquadro <strong>Provvigione</strong> scegli il beneficiario (un contatto qualsiasi, non solo un cliente).</li>
  <li>Indica la percentuale sull'imponibile. <code>0</code> significa nessuna provvigione.</li>
  <li>Salva: la scheda mostra importo e percentuale.</li>
</ol>
<p>Quando il preventivo diventa ordine, la provvigione segue l'ordine
automaticamente.</p>

<h3>Il resoconto mensile</h3>
<p>La pagina <strong>Provvigioni</strong> mostra, per il mese scelto:</p>
<ul>
  <li><strong>Provvigioni del mese</strong>: totale da riconoscere.</li>
  <li><strong>Imponibile di riferimento</strong>: vendite su cui è calcolata.</li>
  <li><strong>Da liquidare</strong>: ordini non ancora consegnati.</li>
  <li><strong>Maturate</strong>: ordini consegnati.</li>
</ul>
<p>La tabella «A chi va riconosciuta» raggruppa per beneficiario; sotto c'è il
dettaglio degli ordini e il riepilogo dell'anno.</p>

<h3>Filtro per stato</h3>
<p>Puoi vedere tutti gli ordini, solo i consegnati o solo quelli in lavorazione.
Il mese di maturazione è quello della consegna per gli ordini consegnati, quello
dell'ordine per quelli ancora in lavorazione.</p>

<h3>Effetto sul margine</h3>
<p>La provvigione è calcolata sull'imponibile ed è sottratta dal margine nelle
statistiche. Il margine mostrato nelle schede è quindi al netto della
provvigione.</p>

<div class="guida-avviso">La provvigione non genera automaticamente una fattura
al beneficiario: il resoconto serve per calcolarla e liquidarla. Per la
contabilità usa i documenti che emetti all'agente o all'agenzia.</div>
""",
    },
]
