"""Guide del magazzino: giacenze, movimenti, rettifiche."""

from .base import SOLO_MAGAZZINO, VENDITE_ACQUISTI

PAGINE = [
    {
        "slug": "magazzino",
        "title": "Magazzino: giacenze, movimenti e scorte",
        "area": "Magazzino",
        "roles": SOLO_MAGAZZINO,
        "order": 10,
        "summary": "Come si legge una giacenza, cosa muove il magazzino e come trovare gli articoli sotto scorta.",
        "body": """
<p>La sezione <strong>Magazzino</strong> tiene la giacenza degli articoli gestiti
a magazzino, per magazzino. Ogni carico, scarico e rettifica lascia un
<strong>movimento</strong> tracciato.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-magazzino.svg" alt="Movimenti di magazzino" loading="lazy">
  <figcaption>Carichi, scarichi e rettifiche aggiornano la stessa giacenza e lasciano un movimento.</figcaption>
</figure>

<h3>Giacenze</h3>
<p>L'elenco mostra articolo, giacenza attuale, scorta minima e stato. Il filtro
<strong>Sotto scorta</strong> mostra solo gli articoli da riordinare (giacenza
sotto la scorta minima). La ricerca cerca per nome o codice.</p>
<p>La colonna <strong>Giacenza</strong> è quella del magazzino scelto;
<strong>Totale articolo</strong> somma tutti i magazzini. Se hai più magazzini,
la scheda articolo mostra la quantità per ciascuno.</p>

<h3>Movimenti</h3>
<p>Ogni movimento ha data, tipo (carico, scarico, rettifica), quantità,
magazzino, riferimento al documento e utente. I filtri permettono di cercare
per articolo, tipo, magazzino o numero di documento.</p>
<ul>
  <li><strong>Carico</strong>: ricezione merce da un ordine fornitore.</li>
  <li><strong>Scarico</strong>: DDT emesso o consegna di un ordine cliente.</li>
  <li><strong>Rettifica</strong>: inventario, rottura, reso, errore di conteggio.</li>
</ul>

<h3>Articoli sotto scorta</h3>
<p>Un articolo è sotto scorta quando la giacenza scende sotto la
<strong>scorta minima</strong> impostata nella scheda. Il gestionale lo
evidenzia in dashboard, nell'elenco articoli e nella pagina giacenze. Il
riordino automatico può includerlo alla conferma di un ordine cliente.</p>

<h3>Cosa non muove il magazzino</h3>
<ul>
  <li>Articoli <strong>non gestiti a magazzino</strong>: servizi, manodopera, trasporti.</li>
  <li><strong>Kit</strong>: si scaricano i componenti, non il kit.</li>
  <li>Righe di testo (sezioni, note).</li>
</ul>

<h3>Giacenza negativa</h3>
<p>Il gestionale impedisce uno scarico che renderebbe negativa la giacenza. Se
succede, significa che la merce non è stata caricata o che la quantità è
sbagliata: controlla i movimenti e la ricezione, non forzare lo scarico.</p>

<div class="guida-avviso">La rettifica non è un modo per «far quadrare» i
conti: serve a correggere un conteggio reale. Scrivi sempre il motivo, così chi
legge i movimenti capisce cosa è successo.</div>
""",
    },
    {
        "slug": "giacenze-consultare",
        "title": "Giacenze: consultare senza modificare",
        "area": "Magazzino",
        "roles": VENDITE_ACQUISTI,
        "order": 15,
        "summary": "Per vendite e acquisti: controllare disponibilità e movimenti prima di promettere una consegna.",
        "body": """
<p>Prima di confermare una consegna o un ordine, controlla la disponibilità
reale. La sezione <strong>Magazzino</strong> è consultabile anche da chi non ha
il ruolo Magazzino.</p>

<h3>Cosa controllare</h3>
<ul>
  <li><strong>Giacenza attuale</strong>: somma di tutti i magazzini.</li>
  <li><strong>Scorta minima</strong>: sotto quel valore l'articolo è da riordinare.</li>
  <li><strong>Movimenti</strong>: gli ultimi carichi e scarichi, con il documento collegato.</li>
  <li><strong>Scheda articolo</strong>: giacenza per magazzino, listini e movimenti.</li>
</ul>

<h3>Prima di promettere una consegna</h3>
<ol>
  <li>Cerca l'articolo per codice o nome.</li>
  <li>Controlla la giacenza e i movimenti recenti: una merce in arrivo non è ancora disponibile.</li>
  <li>Se la giacenza non basta, segnala ad Acquisti o Magazzino: servirà un ordine fornitore o una ricezione.</li>
  <li>Non modificare la giacenza: la rettifica è riservata a Magazzino e Amministratore.</li>
</ol>

<div class="guida-suggerimento">La colonna «Ricevuta» dell'ordine cliente
mostra la merce arrivata dal fornitore e non ancora consegnata: è un'informazione
utile per capire cosa puoi consegnare subito.</div>
""",
    },
    {
        "slug": "rettifica-inventario",
        "title": "Rettifica di inventario",
        "area": "Magazzino",
        "roles": SOLO_MAGAZZINO,
        "order": 30,
        "summary": "Correggere la giacenza con il conteggio reale, lasciando un movimento e un motivo.",
        "body": """
<p>La rettifica serve quando la giacenza del gestionale non corrisponde alla
merce contata in magazzino. Non cancella la storia: registra un movimento di
rettifica con la differenza.</p>

<h3>Quando usarla</h3>
<ul>
  <li>Inventario periodico.</li>
  <li>Merce rotta, persa o non più utilizzabile.</li>
  <li>Reso a fornitore o a cliente non registrato con un documento.</li>
  <li>Errore di conteggio in una ricezione o in un DDT.</li>
</ul>
<p>Non usarla per «nascondere» una consegna o una ricezione mancante: prima
controlla i movimenti e il documento collegato.</p>

<h3>Procedura</h3>
<ol>
  <li>Apri <em>Magazzino → Rettifica</em> (oppure «Rettifica giacenza» dalla
  scheda articolo).</li>
  <li>Scegli l'<strong>articolo</strong> e il <strong>magazzino</strong>.</li>
  <li>Il gestionale mostra la giacenza attuale.</li>
  <li>Inserisci la <strong>nuova giacenza</strong>, cioè la quantità reale contata (non la differenza).</li>
  <li>Scrivi il <strong>motivo</strong>: «inventario annuale», «rotto», «reso», «errore conteggio». È obbligatorio.</li>
  <li>Salva: la differenza diventa un movimento di rettifica.</li>
</ol>

<h3>Cosa succede</h3>
<ul>
  <li>La giacenza viene aggiornata al valore contato.</li>
  <li>Viene creato un movimento di tipo <strong>Rettifica</strong>, con la differenza (positiva o negativa).</li>
  <li>Il movimento resta nella storia dell'articolo con utente e data.</li>
  <li>Se la nuova quantità è uguale a quella attuale, non viene registrato nulla.</li>
</ul>

<h3>Controlli dopo la rettifica</h3>
<ol>
  <li>Apri il movimento e verifica quantità e motivo.</li>
  <li>Controlla che la giacenza sia quella che ti aspetti.</li>
  <li>Se hai sbagliato, registra una seconda rettifica con il valore corretto e un motivo chiaro: non eliminare il movimento.</li>
</ol>

<div class="guida-avviso">La rettifica non corregge il documento che ha causato
l'errore. Se il problema è una ricezione o un DDT sbagliato, sistema il
documento e poi rettifica solo se resta una differenza reale.</div>
""",
    },
]
