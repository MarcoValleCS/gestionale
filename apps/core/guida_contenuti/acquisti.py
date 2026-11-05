"""Guide degli acquisti: ordini fornitore, ricezione, listini, fatture ricevute, import listini."""

from .base import ACQUISTI_MAGAZZINO, SOLO_ACQUISTI, SOLO_ADMIN, SOLO_MAGAZZINO

PAGINE = [
    {
        "slug": "ordini-fornitore",
        "title": "Ordini fornitore",
        "area": "Acquisti",
        "roles": SOLO_ACQUISTI,
        "order": 10,
        "summary": "Creare, inviare, confermare e ricevere un ordine fornitore, anche generato da un ordine cliente.",
        "body": """
<p>Gli ordini fornitore si creano a mano oppure automaticamente quando confermi
un ordine cliente (riordino delle carenze e delle scorte minime). Da qui si
controlla cosa è stato ordinato, a che prezzo e quando arriva.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-acquisti.svg" alt="Flusso degli acquisti" loading="lazy">
  <figcaption>Dal fabbisogno alla ricezione, fino alla fattura e al pagamento.</figcaption>
</figure>

<h3>Creare un ordine fornitore</h3>
<ol>
  <li><em>Acquisti → Ordini fornitore → Nuovo ordine fornitore</em>.</li>
  <li>Scegli il <strong>fornitore</strong>, la data e la consegna prevista.</li>
  <li>Collega il <strong>cantiere</strong> se la merce serve per un lavoro specifico.</li>
  <li>Inserisci le righe: articolo, quantità, prezzo di acquisto (proposto dal
  listino attivo del fornitore, se c'è), IVA. Puoi usare anche righe di testo
  (sezioni, note).</li>
  <li>Salva e, quando è pronto, segna l'ordine come <strong>Inviato</strong>.</li>
</ol>

<h3>Inviare al fornitore o all'agenzia</h3>
<p>Nella scheda dell'ordine puoi inviare l'ordine per email con il PDF in
allegato. Se il fornitore ha un'<strong>agenzia</strong> con email, puoi
scegliere se mandare l'ordine all'agenzia o direttamente al fornitore. L'invio
passa da una coda e parte entro pochi minuti.</p>
<p>Il pulsante <strong>Segna come inviato</strong> cambia lo stato in «Inviato»
anche se hai inviato il PDF con un altro sistema.</p>

<h3>Conferma del fornitore</h3>
<p>Quando il fornitore conferma, premi <strong>Confermato dal fornitore</strong>.
Lo stato serve a distinguere un ordine ancora da concordare da uno che arriverà
davvero.</p>

<h3>Ricevere la merce</h3>
<ol>
  <li>Apri l'ordine e premi <strong>Ricevi merce</strong>.</li>
  <li>Indica le quantità arrivate, anche parziali, e il numero del DDT del fornitore.</li>
  <li>Premi <strong>Registra ricezione e carica magazzino</strong> (oppure
  <strong>Ricevi tutto</strong> se è arrivato tutto).</li>
  <li>L'ordine passa a «Parzialmente ricevuto» o «Ricevuto»; i movimenti di
  magazzino sono registrati.</li>
</ol>

<h3>Fattura e pagamento</h3>
<p>Dalla scheda dell'ordine puoi premere <strong>Registra fattura</strong>: il
gestionale crea una fattura ricevuta in bozza con le righe dell'ordine. Poi la
registri come «Da pagare» e la trovi nello scadenzario. La guida è in
<a href="/guida/fatture-ricevute/">Fatture ricevute</a>.</p>

<h3>Annullare o eliminare</h3>
<ul>
  <li><strong>Annulla</strong>: disponibile finché non è stato ricevuto nulla.</li>
  <li><strong>Elimina</strong>: solo per gli ordini in bozza.</li>
</ul>

<div class="guida-avviso">Se la merce arriva con un DDT del fornitore e la
fattura arriva dopo, ricevi la merce dall'ordine e registra la fattura quando
arriva, collegandola all'ordine. Non aspettare la fattura per caricare il
magazzino.</div>
""",
    },
    {
        "slug": "ordini-fornitore-consultare",
        "title": "Ordini fornitore: consultare e ricevere",
        "area": "Acquisti",
        "roles": SOLO_MAGAZZINO,
        "order": 15,
        "summary": "Per il magazzino: leggere un ordine, controllare le quantità e registrare la ricezione.",
        "body": """
<p>Il magazzino usa gli ordini fornitore per sapere cosa deve arrivare e per
registrare la merce in ingresso. Non crea né modifica gli ordini: quello è
compito di Acquisti.</p>

<h3>Cosa puoi fare</h3>
<ul>
  <li>Consultare l'elenco e la scheda degli ordini fornitore.</li>
  <li>Vedere fornitore, cantiere, righe, quantità ordinata e già ricevuta.</li>
  <li>Premere <strong>Ricevi merce</strong> e registrare le quantità arrivate.</li>
  <li>Stampare l'ordine o scaricare il PDF.</li>
</ul>

<h3>Cosa non puoi fare</h3>
<ul>
  <li>Creare un ordine fornitore.</li>
  <li>Modificare righe, prezzi o fornitore.</li>
  <li>Inviare l'ordine al fornitore o segnarlo come confermato.</li>
  <li>Annullare o eliminare l'ordine.</li>
  <li>Registrare la fattura ricevuta (è di Acquisti).</li>
</ul>

<h3>Leggere lo stato</h3>
<table>
  <thead><tr><th>Stato</th><th>Cosa significa per il magazzino</th></tr></thead>
  <tbody>
    <tr><td>Bozza</td><td>Non ancora inviato: non aspettarti merce.</td></tr>
    <tr><td>Inviato</td><td>Ordinato, in attesa di conferma o consegna.</td></tr>
    <tr><td>Confermato</td><td>Il fornitore ha confermato: la merce arriverà.</td></tr>
    <tr><td>Parzialmente ricevuto</td><td>Una parte è arrivata; il resto è ancora atteso.</td></tr>
    <tr><td>Ricevuto</td><td>Tutto arrivato e caricato.</td></tr>
    <tr><td>Annullato</td><td>Non arriverà nulla.</td></tr>
  </tbody>
</table>

<h3>Ricevere la merce</h3>
<p>La procedura completa è in <a href="/guida/ricezione-merci/">Ricezione merci</a>.
In breve: apri l'ordine, premi «Ricevi merce», indica le quantità arrivate e il
DDT del fornitore, salva. Il magazzino si carica.</p>

<div class="guida-avviso">Se la merce non corrisponde all'ordine, non forzare la
ricezione: segnala la differenza ad Acquisti. Una ricezione sbagliata muove la
giacenza e va corretta con una rettifica.</div>
""",
    },
    {
        "slug": "ricezione-merci",
        "title": "Ricezione merci e carico a magazzino",
        "area": "Acquisti",
        "roles": ACQUISTI_MAGAZZINO,
        "order": 20,
        "summary": "Ricevere tutto o in parte, indicare il DDT del fornitore e correggere gli errori.",
        "body": """
<p>La ricezione è il momento in cui la merce del fornitore entra in magazzino.
Si fa dall'ordine fornitore, non da una schermata separata.</p>

<h3>Prima di iniziare</h3>
<ul>
  <li>Controlla che l'ordine sia quello giusto: fornitore, numero e cantiere.</li>
  <li>Se hai il DDT del fornitore, tienilo a portata: il numero va scritto nella ricezione.</li>
  <li>Se la merce è arrivata solo in parte, preparati a indicare le quantità reali.</li>
</ul>

<h3>Registrare la ricezione</h3>
<ol>
  <li>Apri l'ordine fornitore e premi <strong>Ricevi merce</strong>.</li>
  <li>La tabella mostra ordinato, già ricevuto, da ricevere e la quantità proposta.</li>
  <li>Correggi le quantità nella colonna <strong>Quantità ora</strong>.</li>
  <li>Scrivi il <strong>DDT fornitore</strong> (facoltativo ma consigliato).</li>
  <li>Premi <strong>Registra ricezione e carica magazzino</strong>.</li>
</ol>

<h3>Cosa succede</h3>
<ul>
  <li>Le quantità arrivano nella <strong>giacenza</strong> del magazzino predefinito.</li>
  <li>Viene registrato un <strong>movimento di carico</strong> per ogni riga, con riferimento all'ordine e al DDT.</li>
  <li>L'ordine passa a «Parzialmente ricevuto» o «Ricevuto».</li>
  <li>L'ordine cliente collegato mostra la quantità ricevuta dal fornitore.</li>
</ul>

<h3>Errori frequenti</h3>
<table>
  <thead><tr><th>Messaggio</th><th>Cosa significa</th><th>Cosa fare</th></tr></thead>
  <tbody>
    <tr><td>«Ricevuti X ma ne mancano solo Y»</td><td>Hai indicato più merce di quella ordinata</td><td>Correggi la quantità o crea un nuovo ordine per l'eccedenza</td></tr>
    <tr><td>«Quantità non valida»</td><td>Hai usato una virgola o un carattere strano</td><td>Scrivi un numero con il punto o la virgola decimale, senza simboli</td></tr>
    <tr><td>«L'ordine non può ricevere merce»</td><td>L'ordine è annullato o già ricevuto</td><td>Controlla lo stato; per un nuovo arrivo crea un nuovo ordine</td></tr>
  </tbody>
</table>

<h3>Ricezione parziale</h3>
<p>Se arriva solo una parte, indica le quantità arrivate e lascia a zero le
altre. L'ordine resta «Parzialmente ricevuto»; quando arriva il resto, ripeti
la ricezione. Non creare un secondo ordine per lo stesso materiale.</p>

<div class="guida-avviso">La ricezione carica il magazzino ma non registra la
fattura. La fattura ricevuta è un documento separato: registrala quando arriva,
così lo scadenzario dei pagamenti è corretto.</div>
""",
    },
    {
        "slug": "listini-fornitori",
        "title": "Listini fornitori: prezzi di acquisto e sconti",
        "area": "Acquisti",
        "roles": SOLO_ACQUISTI,
        "order": 30,
        "summary": "Usare i listini, applicare lo sconto fornitore, adeguare i prezzi e cercare per codice.",
        "body": """
<p>Nei <strong>Listini fornitori</strong> ci sono i prezzi di acquisto dei
produttori, articolo per articolo, con il <strong>codice del fornitore</strong>.
Servono a proporre il prezzo giusto negli ordini e a calcolare il margine.</p>

<h3>Cercare nel listino</h3>
<p>La casella in alto cerca per nome, codice articolo, <strong>codice del
fornitore</strong> e codice a barre. I listini grandi sono divisi in pagine.
L'elenco dei listini si può filtrare per fornitore e per validità.</p>

<h3>Creare un listino</h3>
<ol>
  <li><em>Acquisti → Listini fornitori → Nuovo listino</em>.</li>
  <li>Scegli il fornitore, il nome, la validità dal/al e lo stato attivo.</li>
  <li>Aggiungi gli articoli: cerca per nome o codice, indica il codice del
  fornitore, il prezzo, l'eventuale sconto di riga e la quantità minima.</li>
</ol>

<h3>Lo sconto fornitore</h3>
<p>Il fornitore applica uno sconto sul listino: nel riquadro <strong>Sconto
fornitore</strong> scrivi la percentuale e premi <strong>Applica lo
sconto</strong>. Il gestionale:</p>
<ul>
  <li>aggiorna lo sconto di tutte le voci del listino;</li>
  <li>aggiorna il <strong>prezzo di acquisto</strong> di ogni articolo a «prezzo di listino meno lo sconto»;</li>
  <li>lascia invariato il prezzo di vendita.</li>
</ul>
<p>È l'operazione da fare quando il fornitore comunica uno sconto generale.</p>

<h3>Adeguamento prezzi</h3>
<p>Il riquadro <strong>Adeguamento prezzi del listino</strong> applica una
variazione percentuale a tutte le voci (es. +3% per un aumento generale). La
variazione modifica il prezzo di listino e resta registrata nello storico con
data, percentuale, numero di articoli e utente.</p>
<div class="guida-suggerimento">L'adeguamento cambia il prezzo di listino, non
il prezzo di acquisto salvato sull'articolo. Dopo un adeguamento, applica lo
sconto fornitore o controlla il prezzo di acquisto delle voci più importanti.</div>

<h3>Aggiornare un listino</h3>
<ul>
  <li><strong>Modifica listino</strong>: nome, validità, stato.</li>
  <li><strong>Modifica voce</strong>: prezzo, sconto, codice fornitore, quantità minima.</li>
  <li><strong>Nuovo listino</strong>: quando il fornitore manda il listino nuovo, importalo e aggiorna le voci esistenti.</li>
</ul>

<div class="guida-avviso">Il prezzo di acquisto usato negli ordini fornitore e
nel calcolo del margine è quello dell'articolo, aggiornato con lo sconto del
listino. Se il listino è vecchio, i conti sono sbagliati: controlla la validità
prima di ordinare.</div>
""",
    },
    {
        "slug": "fatture-ricevute",
        "title": "Fatture ricevute",
        "area": "Acquisti",
        "roles": SOLO_ACQUISTI,
        "order": 40,
        "summary": "Registrare le fatture dei fornitori, collegarle agli ordini e tenerne sotto controllo le scadenze.",
        "body": """
<p>Le fatture dei fornitori si registrano qui, collegandole (se serve) agli
ordini di acquisto e al cantiere. Da qui nascono le scadenze dei pagamenti.</p>

<h3>Registrare una fattura</h3>
<ol>
  <li><em>Fatturazione → Fatture ricevute → Nuova fattura ricevuta</em>.</li>
  <li>Scegli il <strong>fornitore</strong>, indica data, numero del documento
  fornitore, data di scadenza e condizioni di pagamento.</li>
  <li>Collega il <strong>cantiere</strong> se la spesa riguarda un lavoro.</li>
  <li>Inserisci le righe: articolo (anche con il codice del fornitore),
  quantità, prezzo e IVA.</li>
  <li>Salva: la fattura resta in <strong>bozza</strong>.</li>
  <li>Premi <strong>Registra (da pagare)</strong>: la fattura entra nello scadenzario.</li>
</ol>

<h3>Crearla da un ordine fornitore</h3>
<p>Apri l'ordine fornitore e premi <strong>Registra fattura</strong>: le righe
si copiano, compreso il prezzo di acquisto. Controlla il numero del documento
fornitore e la data prima di registrare.</p>

<h3>Stati</h3>
<table>
  <thead><tr><th>Stato</th><th>Significato</th></tr></thead>
  <tbody>
    <tr><td>Bozza</td><td>Inserita ma non ancora registrata; si può modificare o eliminare.</td></tr>
    <tr><td>Da pagare</td><td>Registrata, entra nello scadenzario.</td></tr>
    <tr><td>Pagata</td><td>Il pagamento è stato registrato.</td></tr>
    <tr><td>Annullata</td><td>Non conta più nello scadenzario.</td></tr>
  </tbody>
</table>

<h3>Controllare i pagamenti</h3>
<p>Nello <a href="/guida/scadenzario/">Scadenzario</a> la scheda dei pagamenti
mostra cosa va pagato e quando, con le fasce di ritardo. Quando paghi, apri la
fattura e premi <strong>Segna come pagata</strong>.</p>

<div class="guida-avviso">Registra la fattura solo dopo aver controllato che
corrisponda all'ordine e alla merce ricevuta. Una fattura registrata per errore
va annullata o corretta prima di segnarla pagata.</div>
""",
    },
    {
        "slug": "importa-listini",
        "title": "Importare i listini dei fornitori",
        "area": "Acquisti",
        "roles": SOLO_ADMIN,
        "order": 50,
        "summary": "Comando da server per importare listini Excel di Colavene, AXA, AXOR, Lacus, Duplach, Forma Aquae e Cosmic.",
        "body": """
<p>Alcuni listini fornitori arrivano in file Excel con formati diversi. Il
comando <code>importa_listini</code> li legge, crea o aggiorna articoli,
varianti, categorie e voci di listino. È un'operazione da amministratore,
perché va eseguita sul server o sul computer di sviluppo.</p>

<h3>Prima di importare</h3>
<ul>
  <li>Fai un <strong>backup</strong> del database e dei file.</li>
  <li>Prova sempre con <code>--dry-run</code>: mostra cosa verrebbe creato senza scrivere nulla.</li>
  <li>Controlla la data di validità del listino e, se serve, chiudi il precedente.</li>
</ul>

<h3>Comandi disponibili</h3>
<table>
  <thead><tr><th>Fornitore</th><th>Comando</th></tr></thead>
  <tbody>
    <tr><td>Colavene</td><td><code>python manage.py importa_listini colavene --file "listino.xlsx"</code></td></tr>
    <tr><td>AXA</td><td><code>python manage.py importa_listini axa --file "AXA_Listino.xlsx"</code></td></tr>
    <tr><td>AXOR</td><td><code>python manage.py importa_listini axor --file "Listino_AXOR_2027.xlsx" --valido-dal 2027-01-01</code></td></tr>
    <tr><td>AXOR finiture</td><td><code>python manage.py importa_listini axor-finiture --file "Listino_AXOR_Finiture_2027.xlsx" --valido-dal 2027-01-01</code></td></tr>
    <tr><td>Lacus</td><td><code>python manage.py importa_listini lacus --file "listino.xls"</code></td></tr>
    <tr><td>Duplach</td><td><code>python manage.py importa_listini duplach --file "Listino_Prezzi_DUPLACH.xlsx"</code></td></tr>
    <tr><td>Forma Aquae</td><td><code>python manage.py importa_listini forma-aquae --file "LISTINO_ITALIA.xlsx"</code></td></tr>
    <tr><td>Cosmic</td><td><code>python manage.py importa_listini cosmic --file "Cosmic_Price_list_2027.xlsx" --valido-dal 2027-01-01 --chiudi-precedenti</code></td></tr>
  </tbody>
</table>

<h3>Opzioni utili</h3>
<ul>
  <li><code>--dry-run</code>: simulazione, nessuna scrittura.</li>
  <li><code>--ricarico 50</code>: imposta il prezzo di vendita = listino + 50%.</li>
  <li><code>--scorta 2</code>: scorta minima per il riordino automatico (predefinita 0).</li>
  <li><code>--solo-nuovi</code>: non aggiorna gli articoli già presenti.</li>
  <li><code>--valido-dal</code> e <code>--valido-al</code>: validità del listino (AAAA-MM-GG).</li>
  <li><code>--chiudi-precedenti</code>: chiude il giorno prima i listini del fornitore che si sovrappongono.</li>
</ul>

<h3>In produzione (Docker)</h3>
<pre>docker compose exec web python manage.py importa_listini cosmic --file "/app/listini/Cosmic_2027.xlsx" --valido-dal 2027-01-01 --dry-run</pre>
<p>Il file deve essere dentro il contenitore: copialo con <code>docker cp</code>
o mettilo in una cartella montata. Dopo la simulazione, ripeti senza
<code>--dry-run</code>.</p>

<div class="guida-avviso">L'importazione può creare molti articoli e aggiornare
prezzi esistenti. Non lanciarla senza backup e senza aver controllato il
risultato della simulazione.</div>
""",
    },
]
