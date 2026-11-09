"""Guide generali: orientamento, dashboard, ricerca, comunicazione, sicurezza."""

from .base import POSTA, TUTTI, UFFICIO

PAGINE = [
    {
        "slug": "primi-passi",
        "title": "Primi passi: orientarsi nel gestionale",
        "area": "Generale",
        "roles": UFFICIO,
        "order": 10,
        "summary": "La dashboard, il menu, la ricerca, i messaggi e la webapp sul telefono.",
        "body": """
<p>Il gestionale si usa dal browser, senza installare nulla sul computer. In alto a
sinistra c'è il <strong>menu</strong> con le sezioni; in alto a destra la
<strong>ricerca</strong>, il tuo nome e il pulsante per uscire.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/mappa-navigazione.svg" alt="Mappa delle sezioni del gestionale" loading="lazy">
  <figcaption>Le sezioni del gestionale. Il menu mostra solo le voci che il tuo ruolo può usare.</figcaption>
</figure>

<h3>La dashboard</h3>
<p>È la prima pagina che vedi: raccoglie i numeri del periodo (fatturato,
margine, ordini, preventivi aperti, articoli sotto scorta) e i promemoria
(ordini da ricevere, manutenzioni in scadenza, fatture da incassare o pagare).
Il menu <strong>Periodo statistiche</strong> cambia l'intervallo dei numeri;
il grafico si può spostare indietro con le frecce.</p>
<p>La guida completa della dashboard è in <a href="/guida/dashboard/">Dashboard e numeri</a>.</p>

<h3>Cercare qualcosa</h3>
<p>La casella in alto cerca in tutto: articoli (anche per codice fornitore e
codice a barre), contatti, preventivi, ordini, fatture, DDT e cantieri. Scrivi
almeno due lettere e premi Invio. I risultati sono divisi per tipo.</p>

<h3>Il menu e i ruoli</h3>
<p>Ogni utente vede solo le voci del proprio ruolo. Se una pagina ti serve ma
non la vedi, chiedi all'amministratore: non è un errore del browser. La pagina
<a href="/guida/percorso-vendite/">Percorso Vendite</a> (o quella del tuo
ruolo) riassume cosa puoi fare.</p>

<h3>Messaggi e posta</h3>
<p><strong>Messaggi</strong> serve a scriversi fra colleghi dentro il
gestionale. <strong>Posta</strong> (se il tuo ruolo la prevede) è la casella
email aziendale: leggi, rispondi e scarichi gli allegati senza uscire dal
programma.</p>

<h3>Il tuo profilo e la password</h3>
<p>Dal menu con il tuo nome puoi <strong>cambiare la password</strong>. Se l'hai
dimenticata, chiedi all'amministratore di reimpostarla: non esiste un link
automatico via email.</p>

<h3>Sul telefono</h3>
<p>Il gestionale si può installare come app: apri il sito con Chrome (Android)
o Safari (iPhone), poi scegli «Aggiungi a schermata Home». Si apre a tutto
schermo come una app normale. I dettagli sono in
<a href="/guida/pwa-telefono/">Gestionale sul telefono</a>.</p>

<h3>Come leggere i numeri</h3>
<ul>
  <li>Gli importi usano la virgola decimale e il punto per le migliaia: <code>1.234,56 €</code>.</li>
  <li>Le date sono nel formato <code>gg/mm/aaaa</code>.</li>
  <li>Le quantità possono avere decimali (es. <code>7,5</code> ore = 7 ore e 30 minuti).</li>
</ul>

<div class="guida-avviso"><strong>Se qualcosa non torna:</strong> ricarica la pagina
con Ctrl+F5 (Windows) o Cmd+R (Mac). Se il problema resta, segnalalo
all'amministratore dicendo cosa stavi facendo e in quale pagina eri.</div>
""",
    },
    {
        "slug": "dashboard",
        "title": "Dashboard e numeri: leggere l'azienda a colpo d'occhio",
        "area": "Generale",
        "roles": UFFICIO,
        "order": 20,
        "summary": "Cosa misurano i riquadri, come cambiare periodo e come usare i promemoria.",
        "body": """
<p>La dashboard è il cruscotto quotidiano. I numeri si aggiornano quando i
documenti vengono emessi o consegnati: non sono una contabilità ufficiale, ma
servono a capire dove intervenire.</p>

<h3>Le azioni rapide</h3>
<p>In alto ci sono i pulsanti per creare subito un <strong>preventivo</strong>,
un <strong>ordine cliente</strong>, un <strong>ordine fornitore</strong>, un
<strong>articolo</strong> o una <strong>rettifica di giacenza</strong>. I
pulsanti visibili dipendono dal tuo ruolo.</p>

<h3>I promemoria</h3>
<ul>
  <li><strong>Cantieri aperti</strong>: lavori non ancora chiusi o annullati.</li>
  <li><strong>Manutenzioni in scadenza</strong>: interventi programmati nei prossimi 30 giorni.</li>
  <li><strong>Da incassare</strong>: fatture emesse o inviate non ancora pagate, con il totale.</li>
  <li><strong>Da pagare</strong>: fatture ricevute registrate e non ancora pagate.</li>
  <li><strong>DDT in bozza</strong>: documenti di trasporto creati ma non ancora emessi.</li>
  <li><strong>Assenze da approvare</strong>: richieste di ferie o permessi in attesa.</li>
</ul>
<p>Se compare la fascia <strong>Assenti oggi</strong>, elenca i dipendenti con
un'assenza approvata che copre la data di oggi. Alcuni promemoria compaiono
solo se il tuo ruolo gestisce quella parte; l'esportazione Excel è riservata a
Vendite e Amministratore.</p>

<h3>I riquadri economici</h3>
<p>Il <strong>fatturato</strong> è il valore degli ordini cliente
<strong>consegnati</strong>, al netto dell'IVA. Il <strong>margine</strong> è
fatturato meno costo del venduto e provvigioni; la <strong>marginalità</strong>
è il margine diviso per il fatturato. Il <strong>valore magazzino</strong> usa
la giacenza moltiplicata per il prezzo di acquisto.</p>
<div class="guida-suggerimento">Un ordine non consegnato non entra nel
fatturato: se i numeri sembrano bassi, controlla prima gli ordini ancora in
bozza o confermati.</div>

<h3>Grafico e periodo</h3>
<p>Il menu <strong>Periodo statistiche</strong> sceglie fra mese corrente, anno
corrente e ultimi 12 mesi. Il grafico mostra fatturato e margine mese per mese;
i pulsanti <code>1</code>, <code>3</code>, <code>6</code>, <code>12</code>
cambiano l'ampiezza, le frecce spostano la finestra indietro.</p>

<h3>Esportare i dati</h3>
<p>Se il tuo ruolo lo consente, il pulsante <strong>Esporta Excel</strong>
scarica una riga per ogni articolo venduto nel periodo, con cliente, cantiere,
quantità, ricavi e costi. Serve per analisi o per passarli al commercialista.
La guida completa è in <a href="/guida/statistiche-vendite/">Statistiche ed
export</a>.</p>

<h3>Gli elenchi in basso</h3>
<p>Articoli sotto scorta, ultimi preventivi, ultimi ordini e manutenzioni in
scadenza: sono scorciatoie operative. Clicca il titolo o «Vedi tutti» per
aprire l'elenco completo con i filtri.</p>
""",
    },
    {
        "slug": "ricerca",
        "title": "Cercare nel gestionale",
        "area": "Generale",
        "roles": UFFICIO,
        "order": 30,
        "summary": "La ricerca globale, i filtri degli elenchi e come trovare un documento che non si vede.",
        "body": """
<p>La casella di ricerca in alto cerca in tutte le sezioni. È il modo più
rapido per ritrovare un cliente, un articolo o un documento senza ricordare in
quale menu si trova.</p>

<h3>Cosa cerca</h3>
<ul>
  <li><strong>Contatti</strong>: nome, codice, partita IVA, codice fiscale, città, email.</li>
  <li><strong>Articoli</strong>: descrizione, codice, codice a barre, codice del fornitore.</li>
  <li><strong>Preventivi, ordini, DDT, fatture</strong>: numero e nome del cliente o fornitore.</li>
  <li><strong>Cantieri</strong>: codice, nome, cliente, città.</li>
</ul>
<p>Scrivi almeno <strong>due lettere</strong> e premi Invio. La ricerca non
distingue maiuscole e minuscole.</p>

<h3>I filtri degli elenchi</h3>
<p>Ogni sezione ha filtri propri: stato, cliente, fornitore, periodo, tipo,
sotto scorta, categoria, etichetta. I filtri si combinano e restano
nell'indirizzo della pagina: puoi salvare un collegamento a un elenco già
filtrato.</p>

<h3>La ricerca dentro la guida</h3>
<p>La pagina <strong>Guida</strong> ha una ricerca separata: cerca nel titolo,
nel sommario e nel testo delle pagine che il tuo ruolo può leggere. Se cerchi
«sconto» trovi le pagine che ne parlano, non i documenti.</p>

<h3>Non trovo un documento</h3>
<ol>
  <li>Controlla di aver scelto il <strong>periodo</strong> giusto: molti elenchi mostrano prima i documenti recenti.</li>
  <li>Togli i filtri con «Azzera» o ricarica l'elenco senza parametri.</li>
  <li>Verifica lo <strong>stato</strong>: un preventivo convertito non è più in «aperti», un DDT emesso non è più in «bozze».</li>
  <li>Se il documento è di un altro cliente o fornitore, aprilo dalla scheda del contatto: la scheda mostra i documenti collegati.</li>
  <li>Se non lo vedi affatto, potrebbe essere di un'area riservata a un altro ruolo: chiedi all'amministratore.</li>
</ol>

<div class="guida-avviso">La ricerca globale è comoda ma non è un archivio
storico illimitato: per un documento molto vecchio usa l'elenco della sezione,
che conserva tutto.</div>
""",
    },
    {
        "slug": "messaggi",
        "title": "Messaggi fra colleghi",
        "area": "Generale",
        "roles": UFFICIO,
        "order": 40,
        "summary": "Come scrivere a un collega, ritrovare le conversazioni e capire le notifiche.",
        "body": """
<p>I messaggi interni servono per le comunicazioni veloci fra chi usa il
gestionale: «il cliente X ha chiamato», «l'ordine Y è pronto», «mi manca il
prezzo del codice Z».</p>

<h3>Scrivere un messaggio</h3>
<ol>
  <li>Apri <strong>Messaggi</strong> dal menu.</li>
  <li>Scegli il destinatario: l'elenco mostra gli utenti attivi tranne te.</li>
  <li>Scrivi il testo e premi <strong>Invia</strong>.</li>
</ol>

<h3>Rispondere e rileggere</h3>
<p>La pagina mostra le conversazioni con l'ultimo messaggio e il numero di
messaggi non letti. Clicca su una conversazione per vedere tutta la sequenza e
rispondere. I messaggi non letti sono evidenziati e il numero rosso sul menu
indica quanti ne hai.</p>

<h3>Cosa non sono i messaggi</h3>
<ul>
  <li>Non sono email: non arrivano sul telefono e non escono dal gestionale.</li>
  <li>Non sono un registro ufficiale: per le comunicazioni con i clienti usa la <strong>Posta</strong> o l'invio del documento per email.</li>
  <li>Non si possono allegare file: usa la scheda del documento o del cantiere per caricare un allegato.</li>
</ul>

<div class="guida-avviso">I messaggi restano nel gestionale e sono visibili
agli utenti che partecipano alla conversazione. Non scriverci dati sensibili
che non vorresti far leggere a un collega.</div>
""",
    },
    {
        "slug": "posta",
        "title": "Posta: la casella aziendale nel gestionale",
        "area": "Generale",
        "roles": POSTA,
        "order": 50,
        "summary": "Leggere, filtrare, rispondere e scaricare gli allegati della casella aziendale.",
        "body": """
<p>La sezione <strong>Posta</strong> mostra le email della casella aziendale,
scaricate via IMAP. Non sostituisce il programma di posta: serve per vedere
subito le risposte dei clienti e le comunicazioni importanti mentre si lavora
sui documenti.</p>

<h3>I filtri</h3>
<ul>
  <li><strong>Rilevanti</strong>: risposte, email dei colleghi e comunicazioni SDI/PEC. È il filtro predefinito.</li>
  <li><strong>Non lette</strong>: solo le email non ancora aperte.</li>
  <li><strong>Da contatti</strong>: email di clienti o fornitori presenti in anagrafica.</li>
  <li><strong>Con allegati</strong>: solo i messaggi che hanno file.</li>
  <li><strong>Tutte</strong>: anche newsletter e pubblicità.</li>
</ul>

<h3>Leggere e rispondere</h3>
<ol>
  <li>Apri una email dall'elenco: il corpo viene scaricato dal server al momento.</li>
  <li>Premi <strong>Rispondi</strong>, scrivi il testo e invia. La risposta parte
  dalla casella aziendale e l'oggetto diventa «Re: …».</li>
  <li>Gli allegati si scaricano con il pulsante accanto al nome del file.</li>
</ol>

<h3>Scaricare le nuove email subito</h3>
<p>Il pulsante <strong>Scarica nuove email</strong> forza il controllo della
casella senza aspettare il prossimo giro automatico. Se la lettura IMAP non è
configurata, compare un avviso con le variabili da impostare nel file
<code>.env</code>.</p>

<h3>Se una email non arriva</h3>
<ul>
  <li>Controlla di aver premuto <strong>Scarica nuove email</strong>.</li>
  <li>Verifica che il messaggio non sia finito nello spam della casella: il gestionale scarica la cartella configurata (di norma <code>INBOX</code>).</li>
  <li>Se compare un errore di connessione, la casella è momentaneamente irraggiungibile: riprova più tardi e segnalalo se continua.</li>
</ul>

<div class="guida-avviso">La posta del gestionale è in sola lettura rispetto al
server: scarica i messaggi ma non cancella né sposta le email dalla casella
originale. Per archiviazioni e regole usa il programma di posta abituale.</div>
""",
    },
    {
        "slug": "pwa-telefono",
        "title": "Gestionale sul telefono",
        "area": "Generale",
        "roles": TUTTI,
        "order": 60,
        "summary": "Installare la webapp su Android e iPhone, usare la fotocamera e lavorare offline.",
        "body": """
<p>Il gestionale è una <strong>PWA</strong>: si installa come una app, senza
passare da Google Play o App Store. Sul telefono è comodo per registrare le
ore, caricare le foto del cantiere e lavorare direttamente dal cantiere.</p>

<h3>Installare su Android</h3>
<ol>
  <li>Apri il gestionale con <strong>Chrome</strong>.</li>
  <li>Apri il menu del browser (tre puntini) e scegli
  <strong>Installa app</strong> o <strong>Aggiungi a schermata Home</strong>.</li>
  <li>Conferma: comparirà l'icona del gestionale nella schermata Home.</li>
</ol>

<h3>Installare su iPhone</h3>
<ol>
  <li>Apri il gestionale con <strong>Safari</strong>.</li>
  <li>Premi il pulsante <strong>Condividi</strong> (il quadrato con la freccia).</li>
  <li>Scegli <strong>Aggiungi alla schermata Home</strong> e conferma.</li>
</ol>

<h3>Fotocamera e file</h3>
<p>Quando carichi una foto o una bolla, il browser chiede il permesso di
accedere alla fotocamera o ai file. Se lo neghi, potrai comunque scegliere una
foto già scattata dalla galleria. Le immagini vengono ridimensionate
automaticamente, così non consumano troppa rete.</p>

<h3>Quando manca la connessione</h3>
<p>Se il telefono è offline, il gestionale mostra una pagina di fallback. I dati
non vengono salvati in locale: quando torni online ricarica la pagina e
ripeti l'operazione. Le foto scelte ma non ancora inviate potrebbero andare
perse se chiudi il browser.</p>

<div class="guida-avviso">La sessione dura 12 ore dall'accesso. Se usi un
telefono condiviso, esci dal menu del tuo nome quando hai finito.</div>
""",
    },
    {
        "slug": "sicurezza-password",
        "title": "Accessi, password e sicurezza",
        "area": "Generale",
        "roles": TUTTI,
        "order": 70,
        "summary": "Cambiare password, proteggere la sessione e capire i messaggi di errore.",
        "body": """
<p>Ogni pagina del gestionale richiede il login. Il tuo utente appartiene a uno
o più ruoli: i ruoli decidono cosa puoi vedere e cosa puoi modificare.</p>

<h3>Cambiare la password</h3>
<ol>
  <li>Apri il menu con il tuo nome in alto a destra.</li>
  <li>Scegli <strong>Password ed email</strong>.</li>
  <li>Inserisci la password attuale e quella nuova due volte.</li>
</ol>
<p>La password deve avere almeno 10 caratteri, non essere troppo comune, non
essere tutta numerica e non essere uguale al nome utente.</p>

<h3>La sessione</h3>
<p>La sessione dura <strong>12 ore dall'accesso</strong> e non si prolunga a ogni
clic. Dopo 12 ore devi rientrare. Se usi un computer condiviso, esci sempre dal
menu del tuo nome.</p>

<h3>Tentativi di accesso</h3>
<p>Dopo 8 tentativi sbagliati in 5 minuti dallo stesso indirizzo, l'accesso
viene bloccato per qualche minuto. È una protezione automatica: aspetta e
riprova, oppure chiedi all'amministratore.</p>

<h3>Cosa puoi fare con il tuo ruolo</h3>
<p>Il menu mostra solo le voci consentite. Se apri un indirizzo diretto di
un'area che non ti compete, il gestionale risponde con un errore di permesso
(403) o ti riporta alla pagina consentita. Non è un guasto: è la protezione
del ruolo.</p>

<div class="guida-ruolo"><strong>Regole pratiche:</strong> non condividere le
credenziali, non salvare la password su computer pubblici, non inviare dati
sensibili via messaggi interni e segnala subito all'amministratore se sospetti
un accesso non tuo.</div>
""",
    },
    {
        "slug": "errori-comuni",
        "title": "Errori comuni e cosa fare",
        "area": "Generale",
        "roles": TUTTI,
        "order": 80,
        "summary": "Permesso negato, sessione scaduta, conflitto di modifica, email non configurata e altri intoppi.",
        "body": """
<p>Quasi tutti gli errori del gestionale hanno una spiegazione semplice. Qui ci
sono i più frequenti e la prima cosa da provare.</p>

<div class="guida-ruolo"><strong>Se sei un collaboratore esterno:</strong> il tuo
menu mostra solo «I miei rapportini», «Nuovo rapportino», «Foto del cantiere» e
«Guida». Un errore di permesso sulle altre pagine è normale: non devi fare
nulla, torna alla tua area.</div>

<h3>«Non hai i permessi necessari» (403)</h3>
<p>La pagina appartiene a un altro ruolo. Torna alla dashboard e usa il menu:
le voci che vedi sono quelle che puoi usare. Se ti serve davvero quella
funzione, chiedi all'amministratore di aggiungere il ruolo al tuo utente.</p>

<h3>La pagina non esiste (404)</h3>
<p>L'indirizzo è sbagliato oppure la pagina è stata nascosta o eliminata. Usa la
ricerca o torna alla <a href="/guida/">guida</a>. Se stavi aprendo un documento,
potrebbe essere stato cancellato da un altro utente.</p>

<h3>La sessione è scaduta</h3>
<p>Dopo 12 ore dall'accesso devi rientrare. Il gestionale ti riporta alla pagina
di login; dopo l'accesso torni alla pagina che stavi aprendo, se l'indirizzo è
ancora valido.</p>

<h3>«Il documento è stato modificato da un altro utente»</h3>
<p>Due persone hanno salvato lo stesso documento quasi insieme. La seconda
modifica non viene applicata, per non sovrascrivere quella dell'altra persona.
La pagina si ricarica con i dati aggiornati: controlla le differenze e
risalva.</p>

<h3>L'email non parte</h3>
<p>Se compare «Invio email non configurato», mancano le variabili
<code>EMAIL_*</code> nel file <code>.env</code>. Chiedi all'amministratore. Se
l'invio è configurato ma la mail non arriva, controlla la casella spam del
destinatario e la pagina <strong>Posta</strong> per eventuali errori.</p>

<h3>Il PDF non è disponibile</h3>
<p>Il PDF viene generato dal server. Se il sistema non riesce, puoi sempre usare
<strong>Stampa</strong> e scegliere «Salva come PDF» dal browser.</p>

<h3>La pagina è lenta o i numeri non tornano</h3>
<p>Ricarica con Ctrl+F5 (Windows) o Cmd+R (Mac). La dashboard tiene in cache i
numeri per un minuto: dopo una consegna o un incasso può servire un minuto
perché il riquadro si aggiorni.</p>

<div class="guida-avviso">Se il problema resta, scrivi all'amministratore
indicando <strong>pagina</strong>, <strong>ora</strong>, <strong>cosa stavi
facendo</strong> e, se compare, il <strong>testo esatto dell'errore</strong>.
Sono le informazioni che servono per capire il problema.</div>
""",
    },
]
