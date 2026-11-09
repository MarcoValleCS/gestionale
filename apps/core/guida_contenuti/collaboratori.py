"""Guida dell'area riservata ai collaboratori esterni."""

from .base import SOLO_COLLABORATORE

PAGINE = [
    {
        "slug": "il-mio-lavoro",
        "title": "Il mio lavoro: il rapportino dal cantiere",
        "area": "Collaboratori",
        "roles": SOLO_COLLABORATORE,
        "order": 10,
        "summary": "Compilare il rapportino di fine giornata: ore, lavori, spese con lo scontrino e foto.",
        "body": """
<p>A fine giornata compili il <strong>rapportino</strong>: le ore lavorate, i
lavori fatti, le spese che hai sostenuto (con la foto dello scontrino) e
qualche foto del cantiere. L'ufficio lo controlla e lo conferma. Vedi solo i
tuoi rapportini: non hai accesso a clienti, prezzi o documenti.</p>

<h3>Entrare</h3>
<ol>
  <li>Apri il gestionale con le credenziali che ti ha dato l'ufficio.</li>
  <li>Dal menu scegli <strong>I miei rapportini</strong>: vedi i rapportini inviati, le ore del mese e dell'anno e le spese che devi ancora ricevere.</li>
</ol>
<p>Se compare un messaggio che dice che l'utente non è collegato a un
collaboratore, chiedi all'ufficio di collegare il tuo utente alla tua scheda.</p>

<h3>Compilare il rapportino</h3>
<ol>
  <li>Premi <strong>Nuovo rapportino</strong>.</li>
  <li><strong>La giornata</strong>: data, ore lavorate, cantiere e cosa hai fatto.</li>
  <li><strong>Spese</strong>: per ogni scontrino premi «Aggiungi spesa» e indica il tipo (materiale, pranzo, carburante, pedaggi…), l'importo, cosa hai comprato e dove. Scegli <em>Pagata da me</em> se l'hai pagata tu: ti verrà rimborsata. Fotografa lo scontrino.</li>
  <li><strong>Foto del cantiere</strong>: puoi sceglierne più di una insieme.</li>
  <li><strong>Segnalazioni</strong>: problemi, materiale che manca, richieste per l'ufficio.</li>
  <li>Premi <strong>Invia all'ufficio</strong>.</li>
</ol>
<p>Le ore vanno in quarti d'ora: <code>4,5</code> significa 4 ore e 30 minuti.
Se quel giorno non hai lavorato ma hai comprato del materiale, metti
<code>0</code> ore e aggiungi la spesa.</p>

<h3>Cosa succede dopo</h3>
<ul>
  <li><span class="badge text-bg-warning">Da confermare</span>: l'ufficio non l'ha ancora visto. Puoi correggerlo o cancellarlo.</li>
  <li><span class="badge text-bg-danger">Da correggere</span>: l'ufficio te lo ha rimandato. Aprilo: in alto trovi la nota con cosa sistemare. Correggi e invia di nuovo.</li>
  <li><span class="badge text-bg-success">Confermato</span>: ore e spese sono state accettate. Non si può più modificare: se c'è un errore, avvisa l'ufficio.</li>
</ul>

<h3>Le spese da rimborsare</h3>
<p>Il riquadro <strong>Spese da rimborsarti</strong> somma le spese che hai
pagato tu, già confermate dall'ufficio e non ancora rimborsate. Quando l'ufficio
ti rimborsa, spariscono dal totale.</p>

<div class="guida-avviso">Compila il rapportino ogni giorno, non a fine mese:
è più facile ricordare cantieri, ore e scontrini. Senza la foto dello scontrino
il rimborso può essere rifiutato.</div>
""",
    },
    {
        "slug": "foto-bolle-collaboratore",
        "title": "Foto del cantiere e bolle dal telefono",
        "area": "Collaboratori",
        "roles": SOLO_COLLABORATORE,
        "order": 20,
        "summary": "Caricare una foto o una bolla, scegliere il cantiere e correggere un caricamento.",
        "body": """
<p>Dalla voce <strong>Foto del cantiere</strong> puoi caricare le foto del
lavoro e le bolle o i documenti di acquisto. Servono all'ufficio per controllare
l'avanzamento e le spese.</p>

<h3>Caricare una foto o una bolla</h3>
<ol>
  <li>Apri <strong>Foto del cantiere</strong>.</li>
  <li>Scegli cosa stai caricando: <strong>Foto del cantiere</strong> (inizio o fine giornata) oppure <strong>Bolla o documento di acquisto</strong>.</li>
  <li>Premi «Scegli file»: si apre la fotocamera o la galleria del telefono.</li>
  <li>Scatta la foto (o scegli quella già fatta).</li>
  <li>Indica il cantiere e, se serve, una nota.</li>
  <li>Salva.</li>
</ol>

<h3>Cosa viene accettato</h3>
<ul>
  <li>Immagini (JPG, PNG, ecc.) e PDF per le bolle.</li>
  <li>La dimensione massima è 25 MB per file; le foto vengono ridimensionate automaticamente.</li>
  <li>I file eseguibili e i formati pericolosi vengono rifiutati.</li>
</ul>

<h3>Ritrova le tue foto</h3>
<p>Nella pagina vedi le foto del cantiere e l'elenco delle bolle che hai
caricato, con data, cantiere e nota. Puoi aprire il file o eliminarlo se hai
sbagliato.</p>

<h3>Se il caricamento non parte</h3>
<ul>
  <li>Controlla la connessione del telefono.</li>
  <li>Se la foto è troppo grande, scattala di nuovo o scegline una più leggera.</li>
  <li>Se il formato non è accettato, converti la foto in JPG o la bolla in PDF.</li>
  <li>Se il problema continua, avvisa l'ufficio.</li>
</ul>

<div class="guida-avviso">Le foto sono visibili all'ufficio (Vendite, Personale
e Amministratore). Non caricare documenti con dati personali che non servono
per il cantiere.</div>
""",
    },
]
