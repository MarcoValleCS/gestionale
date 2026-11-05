"""Guide dei cantieri: commesse, manutenzioni, foto e bolle, galleria."""

from .base import SOLO_VENDITE, UFFICIO, VENDITE_MAGAZZINO, VENDITE_PERSONALE

PAGINE = [
    {
        "slug": "cantieri",
        "title": "Cantieri: il contenitore del lavoro",
        "area": "Cantieri",
        "roles": UFFICIO,
        "order": 10,
        "summary": "Creare una commessa, collegare documenti, ore e foto, e leggerne l'economia.",
        "body": """
<p>Il <strong>cantiere</strong> (commessa) è il contenitore di un lavoro: raccoglie
preventivi, ordini, ordini fornitore, DDT, fatture, ore, foto, allegati e
manutenzioni. Serve a rispondere a una domanda semplice: «questo lavoro quanto
ci è costato e quanto ha reso?».</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-cantiere.svg" alt="Il cantiere collega documenti, ore e foto" loading="lazy">
  <figcaption>Tutti i documenti e le attività del lavoro si collegano allo stesso cantiere.</figcaption>
</figure>

<h3>Creare un cantiere</h3>
<ol>
  <li><em>Cantieri → Nuovo cantiere</em>.</li>
  <li>Indica nome, cliente, indirizzo, stato, responsabile, date e note.</li>
  <li>Salva: il codice viene generato automaticamente.</li>
</ol>

<h3>Collegare i documenti</h3>
<p>Nei moduli di preventivo, ordine cliente, ordine fornitore, DDT e fattura
c'è il campo <strong>Cantiere</strong>. Scegliendolo, il documento compare
nella scheda del cantiere e contribuisce ai suoi numeri. Se il documento è
nato da un ordine o da un preventivo, il cantiere si eredita.</p>

<h3>La scheda del cantiere</h3>
<ul>
  <li><strong>Cliente e luogo</strong>: indirizzo completo, referente.</li>
  <li><strong>Dettagli</strong>: responsabile, inizio lavori, fine prevista.</li>
  <li><strong>Note</strong> e <strong>allegati</strong> (contratti, planimetrie, certificati).</li>
  <li><strong>Fatturazione</strong>: contratto, acconti, SAL, saldi, fatturato e residuo (per Vendite e Amministratore).</li>
  <li><strong>Schede collegate</strong>: preventivi, ordini, ordini fornitore, manutenzioni.</li>
  <li><strong>Ore e foto</strong>: registrazioni dei dipendenti e dei collaboratori.</li>
</ul>

<h3>Gli stati del cantiere</h3>
<table>
  <thead><tr><th>Stato</th><th>Quando si usa</th></tr></thead>
  <tbody>
    <tr><td>Sopralluogo</td><td>Prima del preventivo, per vedere il posto.</td></tr>
    <tr><td>In preventivazione</td><td>Il preventivo è in preparazione.</td></tr>
    <tr><td>Confermato</td><td>Il cliente ha accettato; il lavoro è programmato.</td></tr>
    <tr><td>In esecuzione</td><td>La squadra sta lavorando.</td></tr>
    <tr><td>Collaudo</td><td>Il lavoro è finito, si controlla.</td></tr>
    <tr><td>Chiuso</td><td>Lavoro concluso e fatturato.</td></tr>
    <tr><td>Annullato</td><td>Lavoro non più attivo.</td></tr>
  </tbody>
</table>

<h3>Chi può fare cosa</h3>
<ul>
  <li><strong>Vendite e Amministratore</strong>: creano e modificano il cantiere, vedono l'economia, creano preventivi e manutenzioni.</li>
  <li><strong>Magazzino</strong>: vede il cantiere, riceve merci e crea DDT collegati; può creare manutenzioni.</li>
  <li><strong>Acquisti</strong>: vede il cantiere e collega ordini fornitore e fatture ricevute.</li>
  <li><strong>Personale</strong>: vede il cantiere e registra ore; non vede prezzi e fatture.</li>
</ul>

<div class="guida-avviso">Un documento senza cantiere non entra nelle statistiche
per cantiere. Se il lavoro è importante, collega sempre i documenti al cantiere
già dal preventivo.</div>
""",
    },
    {
        "slug": "manutenzioni",
        "title": "Manutenzioni programmate",
        "area": "Cantieri",
        "roles": VENDITE_MAGAZZINO,
        "order": 20,
        "summary": "Programmare canoni e interventi ricorrenti, segnare l'esecuzione e creare il preventivo.",
        "body": """
<p>Le <strong>manutenzioni</strong> sono appuntamenti periodici: apertura e
chiusura piscina, tagliandi, canoni, controlli. La dashboard le mostra 30 giorni
prima della scadenza, così non si dimenticano.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-manutenzioni.svg" alt="Flusso delle manutenzioni programmate" loading="lazy">
  <figcaption>Dal piano alla scadenza, all'esecuzione, fino al preventivo per il lavoro successivo.</figcaption>
</figure>

<h3>Creare una manutenzione</h3>
<ol>
  <li><em>Cantieri → Manutenzioni → Nuova manutenzione</em>.</li>
  <li>Indica descrizione, cliente, cantiere (facoltativo), frequenza e prossima esecuzione.</li>
  <li>Se il lavoro ricorrente ha un preventivo tipo, scegli il <strong>modello di preventivo</strong>.</li>
  <li>Salva. La manutenzione compare nell'elenco e in dashboard quando è in scadenza.</li>
</ol>

<h3>Frequenze</h3>
<p>Mensile, bimestrale, trimestrale, semestrale, annuale o personalizzata. La
prossima data si calcola dalla data dell'ultima esecuzione, mantenendo il giorno
del mese quando possibile.</p>

<h3>Segnare l'esecuzione</h3>
<ol>
  <li>Apri la manutenzione o l'elenco.</li>
  <li>Premi <strong>Eseguita</strong>.</li>
  <li>Il gestionale calcola la <strong>prossima scadenza</strong> in base alla frequenza.</li>
</ol>
<p>La nuova data parte dalla scadenza appena eseguita, non dal giorno in cui
premi il pulsante. Se l'intervento è stato fatto in un'altra data, correggi la
prossima esecuzione dopo averlo segnato.</p>

<h3>Creare il preventivo</h3>
<p>Premi <strong>Preventivo</strong>: il gestionale crea un preventivo in bozza
dal modello collegato, con cliente e cantiere già compilati. Poi aggiungi le
righe e invialo.</p>

<h3>Filtri</h3>
<ul>
  <li><strong>Attive</strong>: tutte le manutenzioni attive.</li>
  <li><strong>In scadenza (30 giorni)</strong>: quelle da fare a breve.</li>
  <li><strong>Disattivate</strong>: quelle sospese.</li>
  <li><strong>Tutte</strong>: anche le disattivate.</li>
</ul>

<div class="guida-avviso">Se un cliente disdice il canone, disattiva la
manutenzione invece di eliminarla: conservi lo storico e smetti di ricevere
l'avviso.</div>
""",
    },
    {
        "slug": "foto-bolle",
        "title": "Foto dei cantieri e bolle",
        "area": "Cantieri",
        "roles": VENDITE_PERSONALE,
        "order": 30,
        "summary": "Controllare le foto e le bolle caricate dai collaboratori dal telefono.",
        "body": """
<p>I collaboratori esterni caricano dal telefono le <strong>foto del
cantiere</strong> e le <strong>bolle o documenti di acquisto</strong>. L'ufficio
le ritrova in <em>Cantieri → Foto e bolle</em>.</p>

<h3>Cosa vedi</h3>
<ul>
  <li><strong>Foto dei cantieri</strong>: griglia con anteprima, data, autore, cantiere e nota.</li>
  <li><strong>Bolle e documenti di acquisto</strong>: tabella con data, file, collaboratore, cantiere e nota.</li>
  <li>I filtri permettono di scegliere tipo, collaboratore e cantiere.</li>
</ul>

<h3>Controllare una foto</h3>
<ol>
  <li>Apri la foto cliccando l'anteprima: si apre il file originale.</li>
  <li>Verifica che il cantiere e la nota siano corretti.</li>
  <li>Se la foto non serve, eliminala con il cestino (l'operazione è definitiva).</li>
</ol>

<h3>Controllare una bolla</h3>
<ol>
  <li>Apri il file della bolla.</li>
  <li>Confronta importo e data con la fattura o con il resoconto del collaboratore.</li>
  <li>Se la bolla è illeggibile o sbagliata, chiedi al collaboratore di ricaricarla.</li>
</ol>

<h3>Chi può accedere</h3>
<p>La pagina è visibile a Vendite, Personale e Amministratore. I collaboratori
vedono solo le proprie foto nella loro area. Il Magazzino non vede questa
pagina: per la merce usa i movimenti e le ricezioni.</p>

<div class="guida-avviso">Le foto vengono ridimensionate automaticamente al
caricamento, ma restano file del cantiere: non caricare documenti con dati
personali non necessari.</div>
""",
    },
    {
        "slug": "galleria",
        "title": "Galleria fotografica",
        "area": "Cantieri",
        "roles": UFFICIO,
        "order": 40,
        "summary": "Raccogliere le foto dei lavori, etichettarle e collegarle ai cantieri.",
        "body": """
<p>La <strong>Galleria</strong> è la raccolta delle foto dei lavori: piscine,
bagni, showroom, cantieri conclusi. Si può usare per il sito, per i clienti o
per documentare la qualità del lavoro.</p>

<h3>Caricare le foto</h3>
<ol>
  <li>Apri <em>Cantieri e assistenza → Galleria → Carica foto</em>.</li>
  <li>Scegli una o più immagini.</li>
  <li>Indica titolo, descrizione, cantiere ed etichette.</li>
  <li>Decidi se la foto è <strong>visibile in galleria</strong> o nascosta.</li>
  <li>Salva: le foto compaiono nella griglia.</li>
</ol>

<h3>Etichette</h3>
<p>Le etichette (es. «Piscina», «Bagno», «Showroom») servono a filtrare. Si
scelgono dall'elenco o si scrivono a mano separate da virgola: se non esistono,
vengono create. Una foto può avere più etichette.</p>

<h3>Cercare e filtrare</h3>
<ul>
  <li>Ricerca per titolo o descrizione.</li>
  <li>Filtro per cantiere.</li>
  <li>Filtro per una o più etichette: la foto deve averle tutte.</li>
  <li>Le foto nascoste si vedono solo con la spunta «Anche nascoste» (Vendite e Amministratore).</li>
</ul>

<h3>Modificare o eliminare</h3>
<p>Apri una foto e premi <strong>Modifica</strong> per cambiare titolo,
descrizione, cantiere, etichette o visibilità. L'eliminazione cancella il file:
usala solo per foto sbagliate o doppie.</p>

<h3>Chi può fare cosa</h3>
<ul>
  <li><strong>Vendite e Amministratore</strong>: caricano, modificano, eliminano e vedono le foto nascoste.</li>
  <li><strong>Acquisti, Magazzino e Personale</strong>: vedono la galleria e filtrano, ma non modificano.</li>
  <li><strong>Collaboratore</strong>: non vede la galleria; carica le foto del cantiere dalla sua area.</li>
</ul>

<div class="guida-avviso">Le foto della galleria sono visibili a tutti gli
utenti dell'ufficio. Non caricare immagini di persone o documenti senza il
consenso necessario.</div>
""",
    },
]
