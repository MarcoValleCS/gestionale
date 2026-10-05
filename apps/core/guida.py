"""Contenuti della guida del gestionale.

Ogni pagina dichiara i ruoli che possono leggerla: chi entra trova solo le
istruzioni delle funzioni che può davvero usare. I testi si caricano con
``python manage.py carica_guida`` e poi si possono modificare dal gestionale
(Impostazioni → Guida, oppure dal pulsante «Modifica» in ogni pagina).

Il testo è HTML: titoli (h3), elenchi, grassetto, link. Tutto il resto viene
rimosso al salvataggio.
"""

# Ruoli usati nel gestionale (vedi apps/accounts/permissions.py)
TUTTI = ""
SOLO_UFFICIO = "Vendite, Acquisti, Magazzino, Personale, Amministratore"

PAGINE = [
    {
        "slug": "primi-passi",
        "title": "Primi passi: orientarsi nel gestionale",
        "area": "Generale",
        "roles": TUTTI,
        "order": 10,
        "summary": "La dashboard, la ricerca in alto, i messaggi e la webapp sul telefono.",
        "body": """
<p>Il gestionale si usa dal browser. In alto a sinistra c'è il menu con tutte le
sezioni; in alto a destra la <strong>ricerca</strong> e il tuo nome.</p>

<h3>La dashboard</h3>
<p>È la prima pagina che vedi: mostra i numeri del periodo scelto (fatturato,
ordini, preventivi aperti, articoli sotto scorta) e il grafico dell'andamento.
Con il menu «Periodo» in alto a destra cambi l'intervallo (mese, trimestre, anno…).</p>

<h3>Cercare qualcosa</h3>
<p>La casella di ricerca in alto cerca in <strong>tutto</strong>: articoli (anche per
codice del fornitore e codice a barre), contatti, preventivi, ordini, fatture,
DDT, cantieri. Scrivi almeno due lettere e premi Invio.</p>

<h3>Messaggi fra colleghi</h3>
<p>La voce <strong>Messaggi</strong> serve a scriversi fra di voi: scegli il
destinatario, scrivi il testo e invia. Il pallino rosso sul menu indica i
messaggi non letti.</p>

<h3>Il tuo profilo e la password</h3>
<p>Dal menu con il tuo nome (in alto a destra) puoi <strong>cambiare la password</strong>.
Se hai dimenticato la password, chiedi all'amministratore di reimpostarla.</p>

<h3>Sul telefono</h3>
<p>Il gestionale si può installare come app: apri il sito con Chrome (Android) o
Safari (iPhone), poi scegli «Aggiungi a schermata Home». Si apre a tutto schermo
come una app normale.</p>

<div class="guida-avviso"><strong>Se qualcosa non torna:</strong> ricarica la pagina
con Ctrl+F5 (Windows) o Cmd+R (Mac). Se il problema resta, segnalalo
all'amministratore dicendo cosa stavi facendo.</div>
""",
    },
    {
        "slug": "messaggi",
        "title": "Messaggi fra colleghi",
        "area": "Comunicazione",
        "roles": TUTTI,
        "order": 10,
        "summary": "Come scrivere a un collega e ritrovare le conversazioni.",
        "body": """
<p>I messaggi interni servono per le comunicazioni veloci fra chi usa il
gestionale: «il cliente X ha chiamato», «l'ordine Y è pronto», e così via.</p>

<h3>Scrivere un messaggio</h3>
<ol>
<li>Apri <strong>Messaggi</strong> dal menu.</li>
<li>Scegli il destinatario (l'elenco mostra tutti gli utenti attivi tranne te).</li>
<li>Scrivi il testo e premi <strong>Invia</strong>.</li>
</ol>

<h3>Rispondere e rileggere</h3>
<p>La pagina mostra le conversazioni con l'ultimo messaggio; clicca su una
conversazione per vedere tutti i messaggi e rispondere. I messaggi non letti
sono evidenziati, e il numero in rosso sul menu ti dice quanti ne hai.</p>

<div class="guida-avviso">I messaggi restano nel gestionale: non sono email e non
arrivano sul telefono. Per le comunicazioni con i clienti si usa la
<strong>Posta</strong> o l'invio del preventivo per email.</div>
""",
    },
    {
        "slug": "posta",
        "title": "Posta: la casella aziendale nel gestionale",
        "area": "Comunicazione",
        "roles": "Vendite, Acquisti, Personale, Amministratore",
        "order": 20,
        "summary": "Leggere, rispondere e allegare, senza uscire dal gestionale.",
        "body": """
<p>La sezione <strong>Posta</strong> mostra le email della casella aziendale,
scaricate automaticamente ogni pochi minuti.</p>

<h3>I filtri</h3>
<ul>
<li><strong>Rilevanti</strong>: risposte, email dei colleghi e comunicazioni
SDI/PEC. È il filtro predefinito: le newsletter restano fuori.</li>
<li><strong>Non lette</strong>, <strong>Da contatti</strong> (email di clienti o
fornitori in anagrafica), <strong>Con allegati</strong>, <strong>Tutte</strong>.</li>
</ul>

<h3>Leggere e rispondere</h3>
<ol>
<li>Apri una email dall'elenco: il corpo si scarica dal server al momento.</li>
<li>Premi <strong>Rispondi</strong>, scrivi il testo e invia: la risposta parte
dalla casella aziendale e l'oggetto diventa «Re: …».</li>
<li>Gli allegati si scaricano con il pulsante accanto al nome del file.</li>
</ol>

<h3>Scaricare le nuove email subito</h3>
<p>Il pulsante <strong>Scarica nuove email</strong> forza il controllo della
casella senza aspettare la sincronizzazione automatica.</p>

<div class="guida-avviso">Se compare un avviso di errore di connessione, la
casella è momentaneamente irraggiungibile: riprova più tardi e segnalalo se
continua.</div>
""",
    },
    {
        "slug": "contatti",
        "title": "Contatti: clienti, fornitori e agenti",
        "area": "Anagrafiche",
        "roles": SOLO_UFFICIO,
        "order": 10,
        "summary": "Creare un contatto, cercarlo, etichettarlo e allegare documenti.",
        "body": """
<p>In <strong>Contatti</strong> ci sono clienti, fornitori, agenti e
collaboratori. La stessa scheda può essere più di una cosa: un contatto può
essere cliente <em>e</em> fornitore.</p>

<h3>Cercare un contatto</h3>
<p>La barra in alto cerca per nome, codice, partita IVA, città ed email. I filtri
per tipo (clienti, fornitori, agenti) e per etichetta restringono l'elenco.</p>

<h3>Creare un contatto</h3>
<ol>
<li>Premi <strong>Nuovo contatto</strong> e compila i dati: nome, tipo
(cliente/fornitore/agente), indirizzo, partita IVA e codice fiscale, condizioni di
pagamento e sconto abituale.</li>
<li>Salva: la scheda mostra i documenti collegati (preventivi, ordini, fatture,
cantieri) e gli allegati.</li>
</ol>

<h3>Crearlo al volo da un documento</h3>
<p>Mentre compili un preventivo o un ordine, se il cliente non esiste puoi
crearlo senza cambiare pagina: scrivi il nome nella casella cliente, scegli
<strong>Crea «nome»</strong> dalla tendina e compila i pochi dati richiesti. Il
contatto viene selezionato automaticamente nel documento.</p>

<h3>Etichette</h3>
<p>Le etichette colorate (es. «Showroom», «Cantiere», «Agente») servono a
raggruppare i contatti. Si gestiscono da <em>Impostazioni → Etichette</em> e si
applicano nella scheda del contatto.</p>

<h3>Allegati</h3>
<p>Nella scheda puoi caricare documenti (contratti, visure, schede): restano
collegati al contatto e visibili a chi ha accesso.</p>
""",
    },
    {
        "slug": "articoli",
        "title": "Articoli: il catalogo",
        "area": "Anagrafiche",
        "roles": SOLO_UFFICIO,
        "order": 20,
        "summary": "Creare e trovare gli articoli: codice fornitore, codice a barre, varianti e kit.",
        "body": """
<p>In <strong>Articoli</strong> c'è tutto il catalogo: prodotti, servizi e
composizioni. Ogni articolo ha un codice, un'unità di misura, l'IVA e i prezzi di
vendita e di acquisto.</p>

<h3>Trovare un articolo</h3>
<ul>
<li>La ricerca cerca nel nome, nel <strong>codice articolo</strong>, nel
<strong>codice a barre</strong> e nel <strong>codice del fornitore</strong>
(quello dei listini: es. <code>0201001</code> o <code>BRAC-LPWIE-BL1</code>).</li>
<li>I filtri permettono di vedere solo gli articoli <strong>sotto scorta</strong>,
quelli di un fornitore o di una categoria.</li>
</ul>

<h3>Creare un articolo</h3>
<ol>
<li>Premi <strong>Nuovo articolo</strong>: descrizione, categoria, unità di
misura, IVA di vendita e di acquisto, prezzi, fornitore abituale.</li>
<li>Se conosci il <strong>codice a barre</strong>, inseriscilo: si potrà cercare
anche con quello.</li>
<li>Metti la spunta <strong>Gestito a magazzino</strong> se l'articolo ha una
giacenza da tenere sotto controllo, e indica la <strong>scorta minima</strong>:
sotto quel valore l'articolo viene evidenziato e il riordino automatico ne
propone l'acquisto.</li>
</ol>

<h3>Varianti (colore, finitura, misura)</h3>
<p>Un articolo disponibile in più colori si gestisce come <strong>articolo
principale + varianti</strong>: apri la scheda dell'articolo principale, scrivi i
valori nel riquadro «Varianti» (es. <code>Bianco, Nero, Cromo</code>) e premi
Crea. Ogni variante diventa un articolo a sé, con il suo codice, il suo codice a
barre e i suoi prezzi.</p>

<h3>Kit e composizioni</h3>
<p>Un kit (es. «Kit bagno completo») raggruppa più componenti: si crea come
articolo con la spunta <strong>Kit / composizione</strong>, poi si aggiungono i
componenti con le quantità. Nel preventivo il kit si può espandere per far
uscire i singoli pezzi. A magazzino si scaricano i componenti, non il kit.</p>

<h3>Importare molti articoli</h3>
<p>Da <strong>Articoli → Importa</strong> si carica un file CSV o Excel con
l'elenco degli articoli (c'è il modello da scaricare). Le colonne riconosciute
sono descrizione, codice, categoria, unità, prezzi, IVA, codice a barre, scorta
minima, fornitore ed etichette.</p>
""",
    },
    {
        "slug": "preventivi",
        "title": "Preventivi",
        "area": "Vendite",
        "roles": "Vendite, Amministratore",
        "order": 10,
        "summary": "Preparare, stampare, inviare e seguire un preventivo.",
        "body": """
<p>Il preventivo è il documento con cui si propone un lavoro al cliente.</p>

<h3>Creare un preventivo</h3>
<ol>
<li><strong>Vendite → Preventivi → Nuovo preventivo</strong>.</li>
<li>Scegli il <strong>cliente</strong> (o crealo al volo), il cantiere se serve,
la data e la validità.</li>
<li>Compila le righe: nella colonna <em>Articolo</em> scrivi qualche lettera del
nome o il codice (anche quello del fornitore) e scegli dalla tendina. Descrizione,
quantità, prezzo e IVA si compilano da soli; puoi correggerli.</li>
<li>Usa <strong>Sezione</strong> per raggruppare le righe per ambiente (es.
«Bagno 1»): il subtotale esce in scheda e in stampa.</li>
<li>Salva: i totali vengono ricalcolati dal server.</li>
</ol>

<h3>Il margine in tempo reale</h3>
<p>Il riquadro «Totali» a destra mostra imponibile, IVA, totale e — sotto —
<strong>costo merce, margine e marginalità</strong>. Il costo viene
dall'anagrafica dell'articolo o dal listino del fornitore: è un'indicazione, non
un dato contabile.</p>

<h3>Modelli di preventivo</h3>
<p>Se ci sono righe che usi spesso (es. «Kit bagno tipo»), salva un
<strong>modello</strong> da <em>Vendite → Modelli preventivo</em>: nel modulo del
preventivo lo scegli dall'elenco e le righe si compilano da sole.</p>

<h3>Stampare o inviare per email</h3>
<ul>
<li><strong>Stampa</strong>: apre la versione da stampare o salvare in PDF
(anche il PDF si genera dal browser).</li>
<li><strong>Invia email</strong>: manda il preventivo al cliente con il PDF
allegato. L'indirizzo del cliente viene proposto automaticamente.</li>
</ul>

<h3>Seguire i preventivi</h3>
<p>In <em>Vendite → Da seguire</em> ci sono i preventivi non ancora chiusi, con i
giorni trascorsi: da lì puoi inviare un <strong>sollecito</strong> al cliente o
<strong>convertire il preventivo in ordine</strong> con un click.</p>

<div class="guida-avviso">Lo stato del preventivo (bozza, inviato, accettato,
rifiutato) si cambia dalla scheda o dall'elenco: serve a tenere ordinato il
lavoro e a far tornare i conti delle statistiche.</div>
""",
    },
    {
        "slug": "ordini-cliente",
        "title": "Ordini cliente",
        "area": "Vendite",
        "roles": "Vendite, Acquisti, Magazzino, Amministratore",
        "order": 20,
        "summary": "Confermare l'ordine e far partire il riordino delle scorte.",
        "body": """
<p>L'ordine cliente è la conferma di un lavoro: da qui nascono gli impegni di
magazzino e, se serve, gli ordini ai fornitori.</p>

<h3>Creare un ordine</h3>
<ol>
<li>Puoi partire da un <strong>preventivo</strong> (scheda → «Crea ordine») oppure
da <em>Vendite → Ordini cliente → Nuovo ordine</em>.</li>
<li>Compila le righe come nel preventivo (articolo, quantità, prezzo, IVA).</li>
<li>Salva: l'ordine resta in <strong>bozza</strong> finché non lo confermi.</li>
</ol>

<h3>Confermare l'ordine e il riordino automatico</h3>
<p>Premendo <strong>Conferma ordine</strong> il gestionale controlla la
giacenza di ogni articolo e genera automaticamente gli <strong>ordini
fornitore</strong> per quanto manca. Se scegli anche l'opzione di riordino,
vengono aggiunti al riordino tutti gli articoli <em>sotto scorta minima</em> con
fornitore abituale, per riportarli alla scorta.</p>
<p>Gli articoli senza fornitore abituale vengono elencati a parte: va indicato
il fornitore nella scheda dell'articolo perché il riordino li includa.</p>

<h3>Consegnare</h3>
<p>Quando la merce parte, dall'ordine si crea il <strong>DDT</strong>: il
documento di trasporto scarica il magazzino. La fattura si emette dal DDT (o
dall'ordine, se il cliente non vuole il DDT).</p>

<h3>Stato dell'ordine</h3>
<p>Bozza → Confermato → Parzialmente consegnato → Consegnato (o Annullato). Lo
stato si aggiorna con i documenti collegati, e serve per i filtri e le
statistiche.</p>
""",
    },
    {
        "slug": "ddt",
        "title": "DDT: documenti di trasporto",
        "area": "Fatturazione",
        "roles": SOLO_UFFICIO,
        "order": 10,
        "summary": "Emettere un DDT da un ordine o da zero, e cosa scarica dal magazzino.",
        "body": """
<p>Il DDT accompagna la merce che esce dal magazzino.</p>

<h3>Emettere un DDT</h3>
<ol>
<li>Da un <strong>ordine cliente</strong> confermato: apri l'ordine e premi
<strong>Crea DDT</strong>. Le righe si copiano, le quantità ancora da consegnare
vengono proposte.</li>
<li>Oppure da <em>Fatturazione → DDT → Nuovo DDT</em>, scegliendo cliente e
righe.</li>
<li>Compila i dati di trasporto (causale, vettore, colli, peso) e salva.</li>
</ol>

<h3>Cosa succede al magazzino</h3>
<p>Alla conferma del DDT il gestionale <strong>scarica la giacenza</strong> degli
articoli gestiti a magazzino e registra i movimenti. Gli articoli non gestiti
(servizi, kit) non muovono nulla.</p>

<h3>Fatturare</h3>
<p>Dal DDT si crea la <strong>fattura</strong>: le righe e gli importi vengono
copiati. Più DDT dello stesso cliente si possono raggruppare in una fattura
sola.</p>

<div class="guida-avviso">Il DDT si può stampare o inviare per email come gli
altri documenti, e il numero è progressivo e automatico.</div>
""",
    },
    {
        "slug": "fatture-emesse",
        "title": "Fatture emesse",
        "area": "Fatturazione",
        "roles": "Vendite, Amministratore",
        "order": 20,
        "summary": "Emettere una fattura, numerarla e prepararla per lo SDI.",
        "body": """
<p>La fattura è il documento fiscale della vendita.</p>

<h3>Emettere una fattura</h3>
<ol>
<li>Da un <strong>DDT</strong> (consigliato) o da un ordine: apri il documento e
premi <strong>Crea fattura</strong>.</li>
<li>Oppure da <em>Fatturazione → Fatture emesse → Nuova fattura</em>, con righe
inserite a mano.</li>
<li>Controlla data, condizioni di pagamento (che calcolano la scadenza) e
l'eventuale riferimento al documento di trasporto.</li>
<li>Salva: il numero viene assegnato automaticamente dalla numerazione.</li>
</ol>

<h3>Stampare o inviare</h3>
<p>La fattura si stampa (o si salva in PDF) e si invia per email con il PDF
allegato.</p>

<h3>Scadenze e incassi</h3>
<p>Ogni fattura ha una <strong>scadenza</strong> calcolata dalle condizioni di
pagamento (es. bonifico 30 giorni). Nello <strong>Scadenzario</strong> vedi cosa
scade e cosa è in ritardo; quando il cliente paga, segni l'incasso dalla
fattura.</p>

<div class="guida-avviso">Le fatture elettroniche (SDI) si preparano
dall'apposita sezione della fattura: servono i dati fiscali completi del cliente
(codice destinatario o PEC) e la natura IVA corretta per gli esenti.</div>
""",
    },
    {
        "slug": "fatture-ricevute",
        "title": "Fatture ricevute",
        "area": "Fatturazione",
        "roles": "Acquisti, Amministratore",
        "order": 30,
        "summary": "Registrare le fatture dei fornitori e tenerne sotto controllo le scadenze.",
        "body": """
<p>Le fatture dei fornitori si registrano qui, collegandole (se serve) agli
ordini di acquisto.</p>

<h3>Registrare una fattura</h3>
<ol>
<li><em>Fatturazione → Fatture ricevute → Nuova fattura ricevuta</em>.</li>
<li>Scegli il <strong>fornitore</strong>, indica numero e data del documento,
data di scadenza e condizioni di pagamento.</li>
<li>Inserisci le righe: articolo (anche con il codice del fornitore), quantità,
prezzo e IVA. Se la fattura arriva da un ordine fornitore puoi crearla da lì e le
righe si copiano.</li>
<li>Salva: la scadenza finisce nello scadenzario dei pagamenti.</li>
</ol>

<h3>Controllare i pagamenti</h3>
<p>Nello <strong>Scadenzario</strong> la scheda dei pagamenti mostra cosa va
pagato e quando, con le fasce di ritardo. Quando paghi, segni il pagamento dalla
fattura.</p>
""",
    },
    {
        "slug": "scadenzario",
        "title": "Scadenzario: incassi e pagamenti",
        "area": "Fatturazione",
        "roles": SOLO_UFFICIO,
        "order": 40,
        "summary": "Cosa è in scadenza, cosa è in ritardo e come mandare i solleciti.",
        "body": """
<p>Lo scadenzario tiene insieme le fatture da incassare (clienti) e quelle da
pagare (fornitori).</p>

<h3>Cosa mostra</h3>
<ul>
<li><strong>Incassi</strong>: fatture emesse non ancora pagate, raggruppate per
scadenza e fascia di ritardo (in scadenza, scadute da poco, molto in ritardo).</li>
<li><strong>Pagamenti</strong>: fatture ricevute da pagare, con le stesse fasce.</li>
</ul>

<h3>Segnare un incasso o un pagamento</h3>
<p>Apri la fattura dallo scadenzario e premi <strong>Segna come pagata</strong>
(indicando la data). La fattura esce dallo scadenzario.</p>

<h3>Solleciti</h3>
<p>Dalle righe in ritardo puoi inviare un <strong>sollecito di pagamento</strong>
per email: il testo è già pronto e si può modificare prima di inviare.</p>
""",
    },
    {
        "slug": "ordini-fornitore",
        "title": "Ordini fornitore e ricezione merci",
        "area": "Acquisti",
        "roles": "Acquisti, Magazzino, Amministratore",
        "order": 10,
        "summary": "Ordinare ai fornitori, ricevere la merce e aggiornare il magazzino.",
        "body": """
<p>Gli ordini fornitore si creano a mano oppure automaticamente quando confermi
un ordine cliente (riordino delle carenze e delle scorte minime).</p>

<h3>Creare un ordine fornitore</h3>
<ol>
<li><em>Acquisti → Ordini fornitore → Nuovo ordine fornitore</em>.</li>
<li>Scegli il <strong>fornitore</strong>, la data e la consegna prevista.</li>
<li>Inserisci le righe: articolo, quantità, prezzo di acquisto (proposto dal
listino del fornitore se presente), IVA. Puoi collegare l'ordine a un cantiere.</li>
<li>Salva e, quando è pronto, segna l'ordine come <strong>inviato</strong>.</li>
</ol>

<h3>Ricevere la merce</h3>
<ol>
<li>Apri l'ordine e premi <strong>Ricevi merci</strong>.</li>
<li>Indica le quantità arrivate (anche parziali): il magazzino viene
<strong>caricato</strong> e i movimenti registrati.</li>
<li>L'ordine passa a «parzialmente ricevuto» o «ricevuto».</li>
</ol>

<div class="guida-avviso">Se la merce arriva con un DDT del fornitore e la
fattura arriva dopo, ricevi la merce dall'ordine e registra la fattura quando
arriva, collegandola all'ordine.</div>
""",
    },
    {
        "slug": "listini-fornitori",
        "title": "Listini fornitori: prezzi di acquisto e sconti",
        "area": "Acquisti",
        "roles": "Acquisti, Amministratore",
        "order": 20,
        "summary": "Come si usano i listini, come impostare lo sconto fornitore e come cercare per codice.",
        "body": """
<p>Nei <strong>Listini fornitori</strong> ci sono i prezzi di acquisto dei
produttori, articolo per articolo, con il <strong>codice del fornitore</strong>.</p>

<h3>Cercare nel listino</h3>
<p>La casella in alto cerca per nome, codice articolo, <strong>codice del
fornitore</strong> e codice a barre. I listini grandi sono divisi in pagine.</p>

<h3>Lo sconto fornitore</h3>
<p>Il fornitore applica uno sconto sul listino: nel riquadro <strong>Sconto
fornitore</strong> della pagina del listino scrivi la percentuale e premi
Applica. Il <strong>prezzo di acquisto</strong> di ogni articolo diventa
«prezzo di listino meno lo sconto». Il prezzo di vendita non cambia.</p>

<h3>Aggiornare i prezzi</h3>
<ul>
<li><strong>Adeguamento prezzi</strong>: applica una variazione percentuale a
tutto il listino (es. +3% per un aumento generale). Le variazioni restano
registrate nello storico.</li>
<li><strong>Nuovo listino</strong>: quando il fornitore manda il listino nuovo,
si importa e gli articoli già presenti vengono aggiornati nei prezzi.</li>
</ul>

<h3>Aggiungere un articolo a un listino</h3>
<p>Nel riquadro «Aggiungi articolo» cerca l'articolo (anche per codice
fornitore), indica il codice del fornitore, il prezzo, l'eventuale sconto di
riga e la quantità minima.</p>

<div class="guida-avviso">Il prezzo di acquisto usato negli ordini fornitore e
nel calcolo del margine è quello del listino attivo del fornitore: se il listino
è aggiornato, i conti sono giusti.</div>
""",
    },
    {
        "slug": "magazzino",
        "title": "Magazzino: giacenze, movimenti e inventario",
        "area": "Magazzino",
        "roles": SOLO_UFFICIO,
        "order": 10,
        "summary": "Come si legge una giacenza, cosa muove il magazzino e come fare una rettifica.",
        "body": """
<p>La sezione <strong>Magazzino</strong> tiene la giacenza degli articoli gestiti
a magazzino.</p>

<h3>Giacenze</h3>
<p>L'elenco mostra articolo, giacenza attuale, scorta minima e stato. Il filtro
<strong>Sotto scorta</strong> mostra solo gli articoli da riordinare (giacenza
sotto la scorta minima).</p>

<h3>Movimenti</h3>
<p>Ogni carico e scarico è registrato con data, causale e documento collegato:
ricezione merce, DDT emesso, rettifica di inventario. Da qui si ricostruisce la
storia di un articolo.</p>

<h3>Rettifica di giacenza (inventario)</h3>
<ol>
<li>Apri <strong>Giacenze</strong> e scegli l'articolo (o «Rettifica» dal menu).</li>
<li>Indica la quantità <em>reale</em> contata e una nota (es. «inventario
annuale», «rotto», «reso»).</li>
<li>Salva: la differenza viene registrata come movimento di rettifica.</li>
</ol>

<div class="guida-avviso">I kit non hanno giacenza: si scaricano i componenti.
Gli articoli non gestiti a magazzino (servizi, trasporti) non compaiono qui.</div>
""",
    },
    {
        "slug": "cantieri",
        "title": "Cantieri, manutenzioni e foto",
        "area": "Cantieri",
        "roles": SOLO_UFFICIO,
        "order": 10,
        "summary": "Tenere insieme documenti, ore, foto e appuntamenti di un lavoro.",
        "body": """
<p>Il <strong>cantiere</strong> (commessa) è il contenitore di un lavoro: raccoglie
documenti, ore, spese e foto.</p>

<h3>Creare un cantiere</h3>
<ol>
<li><em>Cantieri → Nuovo cantiere</em>: nome, cliente, indirizzo, stato.</li>
<li>Collega preventivi, ordini, DDT, fatture e ordini fornitore dal campo
«Cantiere» dei documenti: così i costi e i ricavi del lavoro si ritrovano
insieme.</li>
<li>Nella scheda vedi anche le ore registrate e le foto caricate.</li>
</ol>

<h3>Manutenzioni</h3>
<p>Le <strong>manutenzioni</strong> sono appuntamenti periodici (es. apertura e
chiusura piscina): si creano con data, cliente e tipo di intervento, e si
segnano come fatte quando vengono svolte.</p>

<h3>Foto e bolle</h3>
<p>In <em>Cantieri → Foto e bolle</em> ci sono le foto di cantiere e le bolle
caricate dai collaboratori dal telefono, con il cantiere collegato.</p>
""",
    },
    {
        "slug": "personale",
        "title": "Personale: dipendenti, ore e ferie",
        "area": "Personale",
        "roles": "Personale, Amministratore",
        "order": 10,
        "summary": "Anagrafica dipendenti, registrazione ore, ferie e permessi, presenze.",
        "body": """
<p>La sezione <strong>Personale</strong> gestisce dipendenti, ore lavorate,
ferie e permessi.</p>

<h3>Dipendenti</h3>
<p>La scheda contiene i dati anagrafici, la qualifica, l'eventuale utente
collegato, l'<strong>orario standard</strong> (ore giornaliere) e la tariffa
oraria. Le ore standard servono al calcolo delle presenze.</p>

<h3>Registrare le ore</h3>
<ol>
<li><em>Personale → Registrazione ore → Nuova registrazione</em>.</li>
<li>Scegli dipendente, data, ore, il cantiere o l'attività e una nota.</li>
<li>Salva: le ore entrano nei totali del dipendente e del cantiere.</li>
</ol>

<h3>Ferie e permessi</h3>
<p>Le richieste si registrano con tipo (ferie, permesso, malattia), dal/al e
stato. Le richieste approvate vengono conteggiate nel riepilogo.</p>

<h3>Registro presenze</h3>
<p>Il <strong>Registro presenze</strong> mostra mese per mese, per ogni
dipendente, le ore registrate rispetto alle ore standard: le differenze si
vedono a colpo d'occhio.</p>
""",
    },
    {
        "slug": "collaboratori",
        "title": "Collaboratori esterni",
        "area": "Personale",
        "roles": "Personale, Amministratore",
        "order": 20,
        "summary": "Anagrafica, ore, foto dal cantiere e resoconto per la fatturazione.",
        "body": """
<p>I <strong>collaboratori</strong> sono le partite IVA esterne (scavi,
elettricista, piastrellista…).</p>

<h3>Anagrafica</h3>
<p>La scheda contiene dati, specializzazione, contatto, tariffa oraria e
l'eventuale utente collegato per l'accesso al gestionale.</p>

<h3>Cosa fanno dal telefono</h3>
<p>Il collaboratore entra con le sue credenziali e trova solo la sua area:
<strong>registra le ore</strong> sui cantieri e carica <strong>foto del cantiere
o bolle di acquisto</strong>. Le foto vengono ridimensionate automaticamente.</p>

<h3>Resoconto per la fatturazione</h3>
<p>Il resoconto ore per collaboratore e periodo serve a controllare le fatture
che arrivano: si esporta in Excel e si confronta con il documento ricevuto.</p>
""",
    },
    {
        "slug": "statistiche-provvigioni",
        "title": "Statistiche e provvigioni",
        "area": "Numeri",
        "roles": "Vendite, Amministratore",
        "order": 10,
        "summary": "Fatturato, margini, classifiche e calcolo delle provvigioni.",
        "body": """
<h3>Statistiche</h3>
<p>La pagina <strong>Statistiche</strong> mostra, per il periodo scelto:
fatturato, costo merce, margine e marginalità, con le classifiche per articolo,
cliente, fornitore e cantiere. Il periodo si cambia dal menu in alto.</p>

<h3>Provvigioni</h3>
<p>La pagina <strong>Provvigioni</strong> calcola le provvigioni sugli ordini
consegnati, raggruppate per agente e per mese. Ogni ordine può avere un agente e
una percentuale di provvigione: si impostano nella scheda dell'ordine o del
preventivo.</p>
<p>Il resoconto mensile si può esportare per il pagamento.</p>

<div class="guida-avviso">I numeri delle statistiche si basano sugli <strong>ordini
consegnati</strong>: se un ordine non è segnato come consegnato, non entra nel
conteggio.</div>
""",
    },
    {
        "slug": "impostazioni",
        "title": "Impostazioni del gestionale",
        "area": "Impostazioni",
        "roles": "Amministratore",
        "order": 10,
        "summary": "Dati azienda, IVA, unità, etichette, pagamenti, numerazioni, email e utenti.",
        "body": """
<p>Le <strong>Impostazioni</strong> sono riservate all'amministratore: qui si
configura il gestionale.</p>

<h3>Dati azienda</h3>
<p>Ragione sociale, indirizzo, partita IVA, IBAN, logo e le condizioni generali
che compaiono in fondo ai documenti. Da qui si scelgono anche il colore e lo
<strong>stile di stampa</strong> dei documenti.</p>

<h3>Tabelle di base</h3>
<ul>
<li><strong>Aliquote IVA</strong>: aliquote e natura (per la fatturazione
elettronica).</li>
<li><strong>Unità di misura</strong>: pezzi, metri, kg…</li>
<li><strong>Etichette</strong>: le etichette colorate di contatti e articoli.</li>
<li><strong>Condizioni di pagamento</strong>: rimessa diretta, bonifico 30/60
giorni… da cui si calcolano le scadenze.</li>
<li><strong>Numerazioni</strong>: prefissi e numeri di preventivi, ordini,
DDT, fatture.</li>
</ul>

<h3>Email</h3>
<p>La pagina <strong>Email</strong> mostra lo stato dell'invio (SMTP) e della
casella in arrivo (IMAP) e permette di inviare un'email di prova.</p>

<h3>Registro attività</h3>
<p>Il <strong>Registro attività</strong> dice chi ha creato, modificato o
cancellato documenti, articoli e contatti: utile per capire cosa è cambiato e
da chi.</p>

<h3>Utenti e ruoli</h3>
<p>Da <strong>Utenti</strong> si creano gli accessi e si assegnano i ruoli:
Vendite, Acquisti, Magazzino, Personale, Collaboratore, Amministratore. I ruoli
decidono cosa vede e cosa può fare ogni persona.</p>
""",
    },
    {
        "slug": "copia-sicurezza",
        "title": "Copia di sicurezza (backup)",
        "area": "Impostazioni",
        "roles": "Amministratore",
        "order": 20,
        "summary": "Dove sono i backup, come scaricarli e cosa fare se serve ripristinare.",
        "body": """
<p>Ogni notte il gestionale salva una copia del database e dei file caricati.</p>

<h3>Dove sono</h3>
<p>In <em>Impostazioni → Copia di sicurezza</em> vedi l'elenco delle copie
disponibili (database e file), con data e dimensione. Restano sul server 14
giorni.</p>

<h3>Scaricare una copia</h3>
<p>Premi <strong>Scarica</strong> accanto a una copia per salvarla su questo
computer (o su un disco esterno). È importante farlo ogni tanto: se il server
si guasta, le copie sul server andrebbero perse.</p>

<h3>Avvisi automatici</h3>
<p>Il gestionale manda un'email se il backup fallisce, se il disco del server si
riempie o se il sito non risponde. Se ricevi un avviso, c'è qualcosa da
controllare.</p>

<h3>Ripristinare una copia</h3>
<p>Il ripristino si fa sul server, con lo script <code>scripts/restore.sh</code>
(serve l'accesso al server). Prima di ripristinare, fai una copia di quello che
c'è adesso.</p>
""",
    },
    {
        "slug": "il-mio-lavoro",
        "title": "Il mio lavoro: ore e foto dal cantiere",
        "area": "Collaboratori",
        "roles": "Collaboratore",
        "order": 10,
        "summary": "Come registrare le ore e caricare le foto del cantiere dal telefono.",
        "body": """
<p>Da qui registri le ore lavorate e carichi le foto del cantiere o le bolle di
acquisto.</p>

<h3>Registrare le ore</h3>
<ol>
<li>Apri <strong>Il mio lavoro</strong> dal menu.</li>
<li>Indica la data, le ore lavorate, il cantiere (se lo conosci) e una breve
descrizione del lavoro fatto.</li>
<li>Salva. Le ore si possono correggere finché non sono state approvate.</li>
</ol>

<h3>Caricare una foto</h3>
<ol>
<li>Apri <strong>Foto del cantiere</strong>.</li>
<li>Scegli se è una <strong>foto del cantiere</strong> (inizio o fine giornata)
o una <strong>bolla o documento di acquisto</strong>.</li>
<li>Premi «Scegli file»: si apre la fotocamera del telefono. Scatta la foto (o
scegli quella già fatta) e salva.</li>
<li>Se serve, aggiungi una nota e indica il cantiere.</li>
</ol>
<p>Le foto vengono ridimensionate automaticamente: puoi caricarle anche con la
rete del telefono.</p>

<div class="guida-avviso">Vedi solo la tua area: ore, foto e bolle. Prezzi,
clienti e documenti non sono visibili con il profilo collaboratore.</div>
""",
    },
]
