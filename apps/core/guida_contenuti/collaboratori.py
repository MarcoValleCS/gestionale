"""Guida dell'area riservata ai collaboratori esterni."""

from .base import SOLO_COLLABORATORE

PAGINE = [
    {
        "slug": "il-mio-lavoro",
        "title": "Il mio lavoro: ore dal cantiere",
        "area": "Collaboratori",
        "roles": SOLO_COLLABORATORE,
        "order": 10,
        "summary": "Come entrare, registrare le ore, correggerle e leggere i tuoi totali.",
        "body": """
<p>Da questa area registri le ore lavorate sui cantieri. Vedi solo le tue
registrazioni: non hai accesso alle schede clienti, ai prezzi, ai documenti o
alle ore degli altri.</p>

<h3>Entrare</h3>
<ol>
  <li>Apri il gestionale con le credenziali che ti ha dato l'ufficio.</li>
  <li>Dal menu scegli <strong>Le mie ore</strong>.</li>
  <li>La pagina mostra il tuo nome, le ore del mese, dell'anno e il totale.</li>
</ol>
<p>Se compare un messaggio che dice che l'utente non è collegato a un
collaboratore, chiedi all'ufficio di collegare il tuo utente alla tua scheda
collaboratore.</p>

<h3>Registrare le ore</h3>
<ol>
  <li>Premi <strong>Registra le ore</strong>.</li>
  <li>Indica la data, le ore lavorate, il cantiere (se lo conosci) e una breve descrizione del lavoro fatto.</li>
  <li>Salva: le ore compaiono nell'elenco e nei totali.</li>
</ol>
<p>Le ore vanno in quarti d'ora: <code>4,5</code> significa 4 ore e 30 minuti.
Non puoi registrare più di 24 ore in un giorno.</p>

<h3>Correggere o cancellare</h3>
<ul>
  <li>Premi la matita accanto a una registrazione per modificare data, ore, cantiere o descrizione.</li>
  <li>Premi il cestino per cancellarla.</li>
  <li>Puoi modificare o cancellare solo le tue registrazioni.</li>
</ul>
<p>Se una giornata è sbagliata, correggila tu: è più semplice che farla
correggere dall'ufficio.</p>

<h3>I totali</h3>
<ul>
  <li><strong>Ore questo mese</strong>: somma delle ore del mese corrente.</li>
  <li><strong>Ore quest'anno</strong>: somma dall'inizio dell'anno.</li>
  <li><strong>Ore in totale</strong>: tutte le ore registrate.</li>
</ul>

<div class="guida-avviso">Le tue ore vengono controllate dall'ufficio e
confrontate con la tua fattura. Registra le ore giorno per giorno, non tutte
insieme a fine mese: è più facile ricordare i cantieri e le attività.</div>
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
