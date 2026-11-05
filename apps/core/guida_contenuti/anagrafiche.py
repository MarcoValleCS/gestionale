"""Guide delle anagrafiche: contatti, articoli, varianti, import, allegati."""

from .base import ALLEGATI, CONSULTAZIONE, VENDITE_ACQUISTI

PAGINE = [
    {
        "slug": "contatti",
        "title": "Contatti: clienti, fornitori e agenti",
        "area": "Anagrafiche",
        "roles": VENDITE_ACQUISTI,
        "order": 10,
        "summary": "Creare e modificare un contatto, cercarlo, etichettarlo e vedere i documenti collegati.",
        "body": """
<p>In <strong>Contatti</strong> ci sono clienti, fornitori, agenti e
collaboratori. La stessa scheda può essere più di una cosa: un contatto può
essere cliente <em>e</em> fornitore, e può avere un'agenzia collegata.</p>

<h3>Cercare un contatto</h3>
<p>La barra in alto cerca per nome, codice, partita IVA, codice fiscale, città
ed email. I filtri per tipo (clienti, fornitori, agenti), per etichetta e per
stato (attivi/disattivati) restringono l'elenco.</p>

<h3>Creare un contatto</h3>
<ol>
  <li>Premi <strong>Nuovo contatto</strong>.</li>
  <li>Compila i dati: ragione sociale, tipo (cliente e/o fornitore), indirizzo,
  partita IVA e codice fiscale, SDI e PEC, email, telefoni, sito web.</li>
  <li>Indica la <strong>condizione di pagamento</strong> abituale e, per i
  fornitori, lo <strong>sconto acquisto base</strong>.</li>
  <li>Se il contatto ha un'agenzia, compila <strong>Agenzia</strong>,
  <strong>Agente</strong>, telefono ed email: l'ordine fornitore potrà essere
  inviato direttamente all'agenzia.</li>
  <li>Scegli le <strong>etichette</strong> e salva.</li>
</ol>
<p>Il codice viene assegnato automaticamente se lo lasci vuoto.</p>

<h3>La scheda del contatto</h3>
<ul>
  <li><strong>Dati fiscali</strong>: P.IVA, CF, SDI/PEC, condizioni di pagamento e sconto acquisto.</li>
  <li><strong>Contatti</strong>: email, telefono, cellulare, sito.</li>
  <li><strong>Agenzia</strong>: dati dell'agenzia e dell'agente.</li>
  <li><strong>Indirizzo</strong> e <strong>note</strong>.</li>
  <li><strong>Documenti collegati</strong>: preventivi, ordini cliente, ordini fornitore, listini.</li>
</ul>

<h3>Crearlo al volo da un documento</h3>
<p>Mentre compili un preventivo o un ordine, se il cliente non esiste scrivi il
nome nella casella cliente e scegli <strong>Crea «nome»</strong> dalla tendina.
Compila i pochi dati richiesti: il contatto viene creato e selezionato
automaticamente nel documento.</p>

<h3>Disattivare un contatto</h3>
<p>Se un cliente o fornitore non lavora più con te, aprì la scheda e premi
<strong>Disattiva</strong>. Il contatto resta nella storia e nei documenti, ma
non compare più nelle tendine dei nuovi documenti. Puoi riattivarlo in qualsiasi
momento.</p>

<div class="guida-avviso">Non cancellare un contatto che ha documenti: la
disattivazione è la scelta giusta per conservare lo storico. La cancellazione
non è prevista dall'interfaccia.</div>
""",
    },
    {
        "slug": "contatti-consultare",
        "title": "Contatti: consultare le schede",
        "area": "Anagrafiche",
        "roles": CONSULTAZIONE,
        "order": 15,
        "summary": "Per magazzino e personale: trovare un cliente o fornitore e leggere i dati che servono.",
        "body": """
<p>Anche se non crei contatti, puoi consultare l'anagrafica per trovare un
cliente, un fornitore o un recapito. La scheda mostra i dati fiscali, i
contatti, l'indirizzo e i documenti collegati.</p>

<h3>Cercare</h3>
<p>Usa la barra in alto nella sezione <strong>Contatti</strong>: cerca per nome,
codice, partita IVA, città o email. Puoi filtrare per cliente, fornitore,
agente ed etichetta.</p>

<h3>Cosa puoi leggere</h3>
<ul>
  <li>Recapiti: email, telefono, cellulare.</li>
  <li>Dati fiscali: P.IVA, codice fiscale, SDI/PEC.</li>
  <li>Indirizzo e condizioni di pagamento.</li>
  <li>Documenti collegati: preventivi, ordini, listini (se il tuo ruolo può aprirli).</li>
</ul>

<h3>Cosa non puoi fare</h3>
<p>Creare, modificare o disattivare un contatto. Se trovi un dato sbagliato,
segnalalo a Vendite o Acquisti: loro hanno i permessi per correggerlo.</p>

<div class="guida-avviso">Non usare la scheda contatto per comunicazioni
riservate: le note sono visibili a chi ha accesso all'anagrafica.</div>
""",
    },
    {
        "slug": "articoli",
        "title": "Articoli: il catalogo",
        "area": "Anagrafiche",
        "roles": VENDITE_ACQUISTI,
        "order": 20,
        "summary": "Creare e trovare gli articoli: codice, codice a barre, prezzi, IVA, scorta e fornitore.",
        "body": """
<p>In <strong>Articoli</strong> c'è tutto il catalogo: prodotti, servizi e
composizioni. Ogni articolo ha un codice, un'unità di misura, l'IVA e i prezzi
di vendita e di acquisto.</p>

<h3>Trovare un articolo</h3>
<ul>
  <li>La ricerca cerca nel nome, nel <strong>codice articolo</strong>, nel
  <strong>codice a barre</strong> e nel <strong>codice del fornitore</strong>
  (quello dei listini: es. <code>0201001</code> o <code>BRAC-LPWIE-BL1</code>).</li>
  <li>I filtri permettono di vedere solo gli articoli <strong>sotto scorta</strong>,
  quelli di un fornitore, di una categoria o con un'etichetta.</li>
  <li>La scheda mostra giacenze, listini fornitori e ultimi movimenti.</li>
</ul>

<h3>Creare un articolo</h3>
<ol>
  <li>Premi <strong>Nuovo articolo</strong>.</li>
  <li>Compila descrizione, categoria, unità di misura, IVA di vendita e di
  acquisto, prezzi, fornitore abituale e giorni di consegna del fornitore.</li>
  <li>Se conosci il <strong>codice a barre</strong>, inseriscilo: si potrà cercare
  anche con quello.</li>
  <li>Metti la spunta <strong>Gestito a magazzino</strong> se l'articolo ha una
  giacenza da tenere sotto controllo e indica la <strong>scorta minima</strong>.</li>
  <li>Salva: il codice viene generato automaticamente se lo lasci vuoto.</li>
</ol>

<h3>Prezzi di vendita e di acquisto</h3>
<p>Il <strong>prezzo di vendita</strong> è quello proposto nei documenti. Il
<strong>prezzo di acquisto</strong> è il costo usato per il margine e per gli
ordini fornitore. Se il fornitore ha uno sconto base, il gestionale propone il
prezzo di acquisto al netto dello sconto.</p>

<h3>Varianti e kit</h3>
<p>Le varianti (colore, finitura, misura) si creano dalla scheda dell'articolo
principale; i kit si compongono aggiungendo i componenti. Le istruzioni
dettagliate sono in <a href="/guida/varianti-kit/">Varianti e kit</a>.</p>

<h3>Importare molti articoli</h3>
<p>Da <strong>Articoli → Importa</strong> si carica un file CSV o Excel. La
procedura, le colonne riconosciute e gli errori comuni sono in
<a href="/guida/importa-articoli/">Importare articoli</a>.</p>

<div class="guida-avviso">Gli articoli non gestiti a magazzino (servizi,
trasporti, manodopera) non hanno giacenza e non vengono scaricati dai
documenti. I kit non hanno giacenza propria: si scaricano i componenti.</div>
""",
    },
    {
        "slug": "articoli-consultare",
        "title": "Articoli: consultare prezzi e giacenze",
        "area": "Anagrafiche",
        "roles": CONSULTAZIONE,
        "order": 25,
        "summary": "Per magazzino e personale: trovare un articolo, leggerne la giacenza e i movimenti.",
        "body": """
<p>La sezione <strong>Articoli</strong> è consultabile anche da chi non crea
anagrafiche. Serve a rispondere a domande come «quanto ne abbiamo?», «dove sta
quel codice?», «qual è il codice a barre?».</p>

<h3>Cercare un articolo</h3>
<p>Cerca per descrizione, codice articolo, codice a barre o codice del
fornitore. I filtri mostrano solo gli articoli sotto scorta, di una categoria o
di un fornitore.</p>

<h3>Cosa mostra la scheda</h3>
<ul>
  <li><strong>Dati articolo</strong>: unità di misura, prezzi, IVA, fornitore abituale, codice a barre.</li>
  <li><strong>Giacenze per magazzino</strong>: quantità e scorta minima.</li>
  <li><strong>Listini fornitori</strong>: prezzo di listino, sconto e prezzo netto.</li>
  <li><strong>Ultimi movimenti</strong>: carichi, scarichi e rettifiche con riferimento al documento.</li>
</ul>

<h3>Cosa non puoi fare</h3>
<p>Creare o modificare articoli e listini. Se un prezzo o una scorta minima
sono sbagliati, segnalalo ad Acquisti o all'amministratore.</p>

<div class="guida-suggerimento">Se la giacenza è diversa da quella che conti in
magazzino, non modificare l'articolo: usa la
<a href="/guida/rettifica-inventario/">rettifica di inventario</a>, che lascia un
movimento tracciato.</div>
""",
    },
    {
        "slug": "varianti-kit",
        "title": "Varianti e kit",
        "area": "Anagrafiche",
        "roles": VENDITE_ACQUISTI,
        "order": 30,
        "summary": "Come gestire un articolo in più colori e una composizione che si scarica nei componenti.",
        "body": """
<h3>Varianti (colore, finitura, misura)</h3>
<p>Un articolo disponibile in più colori si gestisce come <strong>articolo
principale + varianti</strong>:</p>
<ol>
  <li>Apri la scheda dell'articolo principale.</li>
  <li>Nel riquadro <strong>Varianti</strong> scrivi i valori separati da virgola
  (es. <code>Bianco, Nero, Cromo</code>) e premi <strong>Crea</strong>.</li>
  <li>Ogni variante diventa un articolo a sé, con il suo codice, il suo codice a
  barre e la sua giacenza.</li>
  <li>La variante mostra nella scheda il collegamento all'articolo principale.</li>
</ol>
<p>Le varianti non sono un attributo del kit: si cercano e si vendono come
articoli normali.</p>

<h3>Kit e composizioni</h3>
<p>Un kit (es. «Kit bagno completo») raggruppa più componenti:</p>
<ol>
  <li>Crea un articolo con la spunta <strong>Kit / composizione</strong>.</li>
  <li>Nella scheda, nel riquadro <strong>Componenti del kit</strong>, cerca il
  componente per codice o nome, indica la quantità e aggiungilo.</li>
  <li>Ripeti per tutti i componenti. Puoi rimuoverli con la X accanto al nome.</li>
</ol>

<h3>Cosa succede nei documenti</h3>
<ul>
  <li>Nel preventivo il kit si può espandere: i componenti compaiono come righe a
  prezzo zero e il prezzo resta quello del kit.</li>
  <li>A magazzino si scaricano i <strong>componenti</strong>, non il kit.</li>
  <li>Gli ordini fornitore lavorano sui componenti reali, non sul kit.</li>
  <li>Nella stampa del preventivo il kit può restare una voce sola; negli ordini
  restano i componenti.</li>
</ul>

<div class="guida-avviso">Se un kit non ha componenti, la consegna non può
scaricare nulla. Controlla la composizione prima di venderlo.</div>
""",
    },
    {
        "slug": "importa-articoli",
        "title": "Importare articoli da CSV o Excel",
        "area": "Anagrafiche",
        "roles": VENDITE_ACQUISTI,
        "order": 40,
        "summary": "Colonne riconosciute, modello da scaricare, aggiornamenti e righe scartate.",
        "body": """
<p>L'importazione serve per caricare in una volta articoli, categorie, unità di
misura, fornitori ed etichette. Si trovano in <strong>Articoli →
Importa</strong>.</p>

<h3>Preparare il file</h3>
<ol>
  <li>Scarica il <strong>modello CSV</strong> dalla pagina di importazione.</li>
  <li>Apri il file con Excel o un foglio di calcolo e compila una riga per
  articolo. L'unica colonna obbligatoria è <strong>descrizione</strong>.</li>
  <li>Salva in CSV (separatore virgola o punto e virgola) oppure in Excel
  (<code>.xlsx</code>).</li>
</ol>

<h3>Colonne riconosciute</h3>
<table>
  <thead><tr><th>Colonna</th><th>Obbligatoria</th><th>Cosa contiene</th></tr></thead>
  <tbody>
    <tr><td><code>descrizione</code></td><td>Sì</td><td>Nome dell'articolo</td></tr>
    <tr><td><code>codice</code></td><td>No</td><td>Codice articolo: se esiste, l'articolo viene aggiornato</td></tr>
    <tr><td><code>categoria</code></td><td>No</td><td>Categoria, creata se non esiste</td></tr>
    <tr><td><code>unita_misura</code></td><td>No</td><td>Codice o nome (PZ, KG, H…)</td></tr>
    <tr><td><code>prezzo_vendita</code></td><td>No</td><td>Prezzo di vendita senza IVA</td></tr>
    <tr><td><code>iva_vendita</code></td><td>No</td><td>Codice aliquota o valore (22, 10, N2.2.)</td></tr>
    <tr><td><code>prezzo_acquisto</code></td><td>No</td><td>Prezzo di acquisto senza IVA; con la spunta «Aggiorna il listino» (attiva di default) aggiorna anche la voce di listino</td></tr>
    <tr><td><code>iva_acquisto</code></td><td>No</td><td>Aliquota di acquisto</td></tr>
    <tr><td><code>barcode</code></td><td>No</td><td>Codice a barre / EAN</td></tr>
    <tr><td><code>scorta_minima</code></td><td>No</td><td>Scorta minima per l'avviso sotto scorta</td></tr>
    <tr><td><code>fornitore</code></td><td>No</td><td>Fornitore abituale, creato se non esiste</td></tr>
    <tr><td><code>etichette</code></td><td>No</td><td>Etichette separate da virgola</td></tr>
    <tr><td><code>note</code></td><td>No</td><td>Note interne</td></tr>
    <tr><td><code>attivo</code></td><td>No</td><td>sì / no (predefinito sì)</td></tr>
  </tbody>
</table>

<h3>Come vengono trattate le righe</h3>
<ul>
  <li>Se il <strong>codice</strong> esiste già, l'articolo viene aggiornato; se non
  esiste, viene creato.</li>
  <li>Se il codice è vuoto, il gestionale cerca per descrizione: se la trova,
  aggiorna; altrimenti crea un nuovo articolo.</li>
  <li>Categorie, unità di misura, fornitori ed etichette mancanti vengono creati
  automaticamente.</li>
  <li>Le righe senza descrizione vengono saltate e mostrate nel riepilogo.</li>
</ul>

<h3>Dopo l'importazione</h3>
<p>Controlla il riepilogo: numero di articoli creati, aggiornati, righe scartate
ed eventuali errori. Poi apri qualche scheda a campione per verificare prezzi,
IVA e fornitore.</p>

<div class="guida-avviso">Prima di un import massivo fai una copia del database
o prova il file su pochi articoli. Un codice sbagliato può aggiornare un
articolo esistente invece di crearne uno nuovo.</div>
""",
    },
    {
        "slug": "allegati",
        "title": "Allegati a articoli e cantieri",
        "area": "Anagrafiche",
        "roles": ALLEGATI,
        "order": 50,
        "summary": "Caricare schede tecniche, contratti e documenti, e ritrovarli nella scheda.",
        "body": """
<p>Articoli e cantieri possono avere <strong>allegati</strong>: schede
tecniche, contratti, visure, certificati, foto di documenti. I file restano
collegati alla scheda e si scaricano dal gestionale.</p>

<h3>Caricare un allegato</h3>
<ol>
  <li>Apri la scheda dell'articolo o del cantiere.</li>
  <li>Nel riquadro <strong>Allegati</strong> premi «Scegli file».</li>
  <li>Indica un nome (facoltativo) e una nota, poi salva.</li>
</ol>

<h3>Scaricare o eliminare</h3>
<p>Gli allegati compaiono nell'elenco della scheda con il nome e la data. Il
pulsante di download salva il file sul computer. Solo chi ha caricato il file o
un amministratore dovrebbe eliminarlo: l'eliminazione è definitiva.</p>

<h3>Formati e sicurezza</h3>
<ul>
  <li>I file eseguibili e i formati che il browser può aprire come pagine (HTML, SVG) vengono rifiutati.</li>
  <li>I file si scaricano invece di aprirsi dentro la pagina: è una protezione.</li>
  <li>La dimensione massima è quella configurata dal server (di norma 10 MB per richiesta).</li>
</ul>

<div class="guida-avviso">Non caricare documenti con dati personali non
necessari. Gli allegati sono visibili a tutti gli utenti che possono aprire la
scheda.</div>
""",
    },
]
