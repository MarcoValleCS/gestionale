"""Percorsi guidati per ruolo: cosa fa ogni persona, dall'inizio alla fine."""

from .base import (
    SOLO_ACQUISTI,
    SOLO_ADMIN,
    SOLO_COLLABORATORE,
    SOLO_MAGAZZINO,
    SOLO_PERSONALE,
    SOLO_VENDITE,
)

PAGINE = [
    {
        "slug": "percorso-vendite",
        "title": "Percorso Vendite: dal contatto all'incasso",
        "area": "Percorsi per ruolo",
        "roles": SOLO_VENDITE,
        "order": 10,
        "summary": "La giornata tipo di chi vende: lead, preventivi, ordini, clienti e solleciti.",
        "body": """
<p>Questo percorso è per chi ha il ruolo <strong>Vendite</strong>. Puoi gestire
contatti, articoli, preventivi, ordini cliente, lead, statistiche e provvigioni.
Non puoi creare ordini fornitore o fatture ricevute; il magazzino si muove solo
attraverso i DDT e le consegne che registri.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-vendite.svg" alt="Flusso vendite dal lead all'incasso" loading="lazy">
  <figcaption>Il percorso completo: lead, preventivo, ordine, DDT e fattura. Ogni documento resta collegato al cliente e al cantiere.</figcaption>
</figure>

<h3>Ogni mattina</h3>
<ol>
  <li>Apri la <a href="/guida/dashboard/">dashboard</a>: controlla preventivi aperti, ordini da evadere, fatture da incassare e manutenzioni in scadenza.</li>
  <li>Apri <a href="/guida/follow-up/">Da seguire</a>: i preventivi fermi da più giorni vanno sollecitati o chiusi.</li>
  <li>Apri i <a href="/guida/lead/">Lead</a>: i lead nuovi hanno un pallino rosso nel menu.</li>
  <li>Guarda la <a href="/guida/posta/">Posta</a> per le risposte dei clienti.</li>
</ol>

<h3>Il ciclo completo di una vendita</h3>
<ol>
  <li><strong>Contatto</strong>: cerca il cliente in <a href="/guida/contatti/">Contatti</a>; se non c'è, crealo (o crealo al volo dal preventivo).</li>
  <li><strong>Lead</strong>: se è una trattativa non ancora definita, registrala in <a href="/guida/lead/">Lead</a> con valore stimato e prossima azione.</li>
  <li><strong>Preventivo</strong>: prepara le righe in <a href="/guida/preventivi/">Preventivi</a>, con sezioni, sconti e IVA. Controlla il margine nel riquadro a destra.</li>
  <li><strong>Invio</strong>: stampa o invia il PDF per email. L'invio porta il preventivo da «Bozza» a «Inviato».</li>
  <li><strong>Follow-up</strong>: usa <a href="/guida/follow-up/">Da seguire</a> per sollecitare; quando il cliente accetta, premi «Accettato dal cliente».</li>
  <li><strong>Ordine</strong>: dal preventivo accettato crea l'ordine cliente con «Crea ordine cliente».</li>
  <li><strong>Conferma</strong>: apri l'ordine e premi «Conferma ordine». Se manca merce, il gestionale genera gli ordini fornitore.</li>
  <li><strong>Consegna</strong>: dal menu DDT crea il documento di trasporto; alla consegna il magazzino si scarica.</li>
  <li><strong>Fattura</strong>: crea la fattura dal DDT o dall'ordine, emettila e inviala.</li>
  <li><strong>Incasso</strong>: nello <a href="/guida/scadenzario/">Scadenzario</a> controlla le scadenze e invia i solleciti.</li>
</ol>

<h3>Cosa puoi fare tu</h3>
<table>
  <thead><tr><th>Attività</th><th>Dove</th><th>Note</th></tr></thead>
  <tbody>
    <tr><td>Creare clienti e fornitori</td><td>Contatti</td><td>Anche al volo dai documenti</td></tr>
    <tr><td>Creare articoli e kit</td><td>Articoli</td><td>Prezzi, varianti, import</td></tr>
    <tr><td>Preventivi e modelli</td><td>Vendite</td><td>Stampa, PDF, email, duplica</td></tr>
    <tr><td>Ordini cliente</td><td>Vendite</td><td>Conferma, consegna, annulla</td></tr>
    <tr><td>DDT</td><td>Fatturazione</td><td>Emissione e scarico magazzino</td></tr>
    <tr><td>Fatture emesse</td><td>Fatturazione</td><td>SDI, incassi, solleciti</td></tr>
    <tr><td>Statistiche e provvigioni</td><td>Vendite</td><td>Solo sugli ordini consegnati</td></tr>
  </tbody>
</table>

<h3>Fine mese</h3>
<ul>
  <li>Controlla le <a href="/guida/statistiche-vendite/">statistiche</a> e il margine per cliente e articolo.</li>
  <li>Verifica le <a href="/guida/provvigioni/">provvigioni</a> maturate e da liquidare.</li>
  <li>Sollecita le fatture scadute e segna gli incassi.</li>
  <li>Chiudi o rinnova i preventivi scaduti.</li>
</ul>

<div class="guida-avviso">Il fatturato delle statistiche è calcolato sugli
<strong>ordini consegnati</strong>: se un ordine non è segnato come consegnato,
non entra nei numeri.</div>
""",
    },
    {
        "slug": "percorso-acquisti",
        "title": "Percorso Acquisti: dal fabbisogno al pagamento",
        "area": "Percorsi per ruolo",
        "roles": SOLO_ACQUISTI,
        "order": 20,
        "summary": "Ordinare ai fornitori, ricevere la merce, registrare le fatture e pagare.",
        "body": """
<p>Questo percorso è per chi ha il ruolo <strong>Acquisti</strong>. Puoi gestire
contatti e articoli, ordini fornitore, listini, fatture ricevute e scadenzario
dei pagamenti. Non puoi creare preventivi, ordini cliente o fatture emesse.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-acquisti.svg" alt="Flusso acquisti dal fabbisogno al pagamento" loading="lazy">
  <figcaption>Dal fabbisogno alla ricezione, fino alla fattura e al pagamento.</figcaption>
</figure>

<h3>Ogni mattina</h3>
<ol>
  <li>Controlla gli <strong>ordini fornitore da ricevere</strong> in dashboard.</li>
  <li>Apri <a href="/guida/ricezione-merci/">Ricezione merci</a> per gli arrivi previsti oggi.</li>
  <li>Controlla le <a href="/guida/fatture-ricevute/">fatture ricevute</a> e lo <a href="/guida/scadenzario/">scadenzario</a> dei pagamenti.</li>
  <li>Guarda gli articoli sotto scorta: il riordino può partire anche da un ordine cliente confermato.</li>
</ol>

<h3>Il ciclo completo di un acquisto</h3>
<ol>
  <li><strong>Fabbisogno</strong>: nasce da un ordine cliente confermato, da un articolo sotto scorta o da un ordine inserito a mano.</li>
  <li><strong>Ordine fornitore</strong>: crea l'ordine in <a href="/guida/ordini-fornitore/">Ordini fornitore</a>, con fornitore, cantiere, righe e prezzo di acquisto.</li>
  <li><strong>Invio</strong>: invia l'ordine per email (al fornitore o all'agenzia) e segnalo come «Inviato».</li>
  <li><strong>Conferma</strong>: quando il fornitore conferma, premi «Confermato dal fornitore».</li>
  <li><strong>Ricezione</strong>: alla consegna apri <a href="/guida/ricezione-merci/">Ricevi merce</a>, indica le quantità arrivate e il DDT del fornitore. Il magazzino si carica.</li>
  <li><strong>Fattura</strong>: registra la <a href="/guida/fatture-ricevute/">fattura ricevuta</a>, collegandola all'ordine se possibile.</li>
  <li><strong>Pagamento</strong>: nello scadenzario vedi cosa scade; quando paghi, segna la fattura come pagata.</li>
</ol>

<h3>I listini</h3>
<p>I <a href="/guida/listini-fornitori/">listini fornitori</a> tengono i prezzi di
acquisto e il codice del fornitore. Lo sconto fornitore si applica al listino e
cambia il prezzo di acquisto usato negli ordini e nel margine. I listini si
possono aggiornare con una variazione percentuale o importare da file
(quest'ultima è un'operazione da amministratore).</p>

<h3>Cosa puoi fare tu</h3>
<table>
  <thead><tr><th>Attività</th><th>Dove</th><th>Note</th></tr></thead>
  <tbody>
    <tr><td>Contatti e articoli</td><td>Anagrafiche</td><td>Creazione e modifica</td></tr>
    <tr><td>Ordini fornitore</td><td>Acquisti</td><td>Invio, conferma, ricezione, annulla</td></tr>
    <tr><td>Listini</td><td>Acquisti</td><td>Sconto, adeguamento, storico</td></tr>
    <tr><td>Fatture ricevute</td><td>Fatturazione</td><td>Registrazione e pagamento</td></tr>
    <tr><td>Scadenzario</td><td>Fatturazione</td><td>Solo pagamenti fornitori</td></tr>
    <tr><td>DDT</td><td>Fatturazione</td><td>Solo lettura (<a href="/guida/ddt-consultare/">guida</a>)</td></tr>
  </tbody>
</table>

<div class="guida-avviso">Se un articolo non ha un <strong>fornitore
abituale</strong>, il riordino automatico non può creare l'ordine: il gestionale
lo segnala e l'articolo va completato in anagrafica.</div>
""",
    },
    {
        "slug": "percorso-magazzino",
        "title": "Percorso Magazzino: giacenze, consegne e inventario",
        "area": "Percorsi per ruolo",
        "roles": SOLO_MAGAZZINO,
        "order": 30,
        "summary": "Ricevere la merce, consegnare gli ordini, rettificare le giacenze e tenere i movimenti.",
        "body": """
<p>Questo percorso è per chi ha il ruolo <strong>Magazzino</strong>. Puoi
consultare contatti e articoli, vedere gli ordini, ricevere merce, emettere
DDT, consegnare ordini cliente e rettificare le giacenze. Non puoi creare
preventivi, ordini cliente, fatture o listini.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-magazzino.svg" alt="Movimenti di magazzino" loading="lazy">
  <figcaption>Carichi, scarichi e rettifiche aggiornano la stessa giacenza e lasciano un movimento tracciato.</figcaption>
</figure>

<h3>Ogni mattina</h3>
<ol>
  <li>Apri <strong>Giacenze</strong> e controlla gli articoli sotto scorta.</li>
  <li>Apri <a href="/guida/ricezione-merci/">Ordini fornitore da ricevere</a>: ricevi la merce arrivata.</li>
  <li>Controlla i <strong>DDT in bozza</strong> e le consegne previste.</li>
  <li>Verifica i <strong>movimenti</strong> del giorno per eventuali anomalie.</li>
</ol>

<h3>Le tre operazioni principali</h3>
<ol>
  <li><strong>Carico</strong>: dalla ricezione di un ordine fornitore. Le quantità arrivano in giacenza e viene registrato un movimento.</li>
  <li><strong>Scarico</strong>: dall'emissione di un DDT o dalla consegna di un ordine cliente. La merce esce e il movimento resta collegato al documento.</li>
  <li><strong>Rettifica</strong>: quando il conteggio reale non coincide. Indica la quantità contata e una nota; il gestionale registra la differenza.</li>
</ol>

<h3>Consegnare un ordine cliente</h3>
<ol>
  <li>Apri l'ordine cliente dall'elenco.</li>
  <li>Controlla le quantità e crea il <strong>DDT</strong> con «Crea DDT».</li>
  <li>Apri il DDT, controlla destinazione, vettore e colli, poi premi <strong>Emetti e scarica magazzino</strong>.</li>
  <li>Stampa il DDT e fallo firmare alla consegna.</li>
</ol>
<div class="guida-suggerimento">Se la merce parte senza DDT, puoi usare
«Consegna e scarica magazzino» dalla scheda dell'ordine. Il DDT è comunque
consigliato quando serve la prova di trasporto.</div>

<h3>Rettifica di inventario</h3>
<p>La procedura completa è in <a href="/guida/rettifica-inventario/">Rettifica
di inventario</a>. In breve: apri la rettifica, scegli articolo e magazzino,
inserisci la quantità reale e una nota, salva. La differenza diventa un
movimento di rettifica.</p>

<h3>Cosa puoi fare tu</h3>
<table>
  <thead><tr><th>Attività</th><th>Dove</th><th>Note</th></tr></thead>
  <tbody>
    <tr><td>Giacenze e movimenti</td><td>Magazzino</td><td>Vista completa</td></tr>
    <tr><td>Rettifiche</td><td>Magazzino</td><td>Con nota obbligatoria</td></tr>
    <tr><td>Ricezione merci</td><td>Acquisti</td><td>Anche parziale</td></tr>
    <tr><td>DDT</td><td>Fatturazione</td><td>Creazione, emissione, stampa</td></tr>
    <tr><td>Consegna ordini</td><td>Vendite</td><td>Scarico magazzino</td></tr>
    <tr><td>Contatti e articoli</td><td>Anagrafiche</td><td>Solo lettura</td></tr>
  </tbody>
</table>

<div class="guida-avviso">I kit non hanno giacenza: si scaricano i componenti.
Gli articoli non gestiti a magazzino (servizi, trasporti) non muovono nulla.</div>
""",
    },
    {
        "slug": "percorso-personale",
        "title": "Percorso Personale: dipendenti, ore e assenze",
        "area": "Percorsi per ruolo",
        "roles": SOLO_PERSONALE,
        "order": 40,
        "summary": "Anagrafica dipendenti, registrazione ore, ferie e permessi, presenze e collaboratori.",
        "body": """
<p>Questo percorso è per chi ha il ruolo <strong>Personale</strong>. Gestisci
dipendenti, ore lavorate, ferie e permessi, registro presenze e collaboratori
esterni. Non gestisci preventivi, ordini, fatture o statistiche commerciali; puoi
consultare contatti e articoli quando ti servono.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-personale.svg" alt="Flusso personale e collaboratori" loading="lazy">
  <figcaption>Da una parte i dipendenti, dall'altra i collaboratori esterni; entrambi passano dal cantiere.</figcaption>
</figure>

<h3>Ogni settimana</h3>
<ol>
  <li>Controlla le <strong>assenze da approvare</strong> in dashboard.</li>
  <li>Registra o correggi le ore della squadra con <a href="/guida/registrare-ore/">Registrazione ore</a>.</li>
  <li>Verifica il <a href="/guida/presenze/">Registro presenze</a> del mese.</li>
  <li>Controlla le ore dei <a href="/guida/collaboratori/">collaboratori</a> e le bolle caricate.</li>
</ol>

<h3>Il ciclo delle ore</h3>
<ol>
  <li><strong>Anagrafica</strong>: ogni dipendente ha contratto, ore settimanali, costo orario e ferie/permessi annui.</li>
  <li><strong>Registrazione</strong>: inserisci data, ore, tipo (ordinario, straordinario, trasferta), cantiere e descrizione.</li>
  <li><strong>Inserimento rapido</strong>: «Ore del giorno» registra in una volta le ore di tutta la squadra.</li>
  <li><strong>Presenze</strong>: il registro mensile confronta ore e assenze giorno per giorno.</li>
  <li><strong>Ferie e permessi</strong>: la richiesta nasce in stato «Richiesta», poi si approva o si rifiuta; le ore approvate entrano nel conteggio.</li>
</ol>

<h3>I collaboratori esterni</h3>
<p>I collaboratori (partite IVA) hanno un'anagrafica propria e, se collegati a
un utente, possono entrare dal telefono e registrare ore e foto. L'ufficio
controlla le ore e le usa per confrontare le fatture ricevute. La procedura è
in <a href="/guida/collaboratori/">Collaboratori esterni</a>.</p>

<h3>Cosa puoi fare tu</h3>
<table>
  <thead><tr><th>Attività</th><th>Dove</th><th>Note</th></tr></thead>
  <tbody>
    <tr><td>Dipendenti</td><td>Personale</td><td>Anagrafica, contratto, costi</td></tr>
    <tr><td>Ore</td><td>Personale</td><td>Singole, giornaliere, standard</td></tr>
    <tr><td>Ferie e permessi</td><td>Personale</td><td>Approvazione e residui</td></tr>
    <tr><td>Presenze</td><td>Personale</td><td>Registro mensile</td></tr>
    <tr><td>Collaboratori</td><td>Personale</td><td>Anagrafica, ore, foto</td></tr>
    <tr><td>Contatti e articoli</td><td>Anagrafiche</td><td>Solo lettura</td></tr>
  </tbody>
</table>

<div class="guida-avviso">Le ferie e i permessi approvati compaiono nel registro
presenze con le sigle F, P, M, N, A. Se una richiesta è sbagliata, modificala
prima di approvarla.</div>
""",
    },
    {
        "slug": "percorso-amministratore",
        "title": "Percorso Amministratore: configurare e controllare",
        "area": "Percorsi per ruolo",
        "roles": SOLO_ADMIN,
        "order": 50,
        "summary": "Impostazioni, utenti e ruoli, email, backup, aggiornamenti e supervisione dei processi.",
        "body": """
<p>Il ruolo <strong>Amministratore</strong> vede tutto e può configurare il
gestionale. Le pagine di questa guida sono scritte per essere lette una volta e
poi usate come riferimento.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/ruoli-permessi.svg" alt="Matrice dei permessi per ruolo" loading="lazy">
  <figcaption>Chi può fare cosa. P = accesso completo, M = crea e modifica, L = solo lettura, — = non disponibile.</figcaption>
</figure>
<p>La matrice è una sintesi: il <strong>Magazzino</strong>, oltre alla lettura,
può ricevere merce sugli ordini fornitore e consegnare gli ordini cliente. Il
<strong>Personale</strong> può consultare contatti e articoli ma non modificarli.</p>

<h3>La configurazione iniziale</h3>
<ol>
  <li><a href="/guida/dati-azienda/">Dati azienda</a>: ragione sociale, P.IVA, PEC, regime fiscale, logo, colori e condizioni stampate.</li>
  <li><a href="/guida/tabelle-base/">Tabelle di base</a>: aliquote IVA, unità di misura, etichette, condizioni di pagamento.</li>
  <li><a href="/guida/numerazioni/">Numerazioni</a>: prefissi e progressivi di preventivi, ordini, DDT e fatture.</li>
  <li><a href="/guida/utenti-ruoli/">Utenti e ruoli</a>: crea gli accessi e assegna i gruppi.</li>
  <li><a href="/guida/email-configurazione/">Email</a>: SMTP, IMAP, modelli e prova di invio.</li>
  <li><a href="/guida/copia-sicurezza/">Copia di sicurezza</a>: verifica che i backup girino e scaricali.</li>
</ol>

<h3>Ogni settimana</h3>
<ul>
  <li>Controlla il <a href="/guida/registro-attivita/">Registro attività</a> per modifiche o cancellazioni impreviste.</li>
  <li>Verifica che i backup siano presenti e recenti.</li>
  <li>Controlla gli avvisi automatici (backup fallito, disco pieno, sito irraggiungibile).</li>
  <li>Rivedi gli utenti attivi e i ruoli: togli l'accesso a chi non lavora più.</li>
</ul>

<h3>Ogni mese</h3>
<ul>
  <li>Scarica una copia del database e dei file su un computer o disco esterno.</li>
  <li>Controlla le statistiche e le provvigioni con il responsabile vendite.</li>
  <li>Verifica le scadenze di incasso e pagamento.</li>
  <li>Se serve, aggiorna il gestionale con la procedura di <a href="/guida/aggiornare-gestionale/">Aggiornamento</a>.</li>
</ul>

<h3>Le regole da non dimenticare</h3>
<ul>
  <li>Un utente con <strong>solo</strong> il ruolo Collaboratore viene reindirizzato alla sua area: non vede le schede clienti, i prezzi o i documenti.</li>
  <li>La guida è filtrabile per ruolo: le pagine che scrivi con «Ruoli» compilati sono visibili solo a quei gruppi.</li>
  <li>Il server MCP, se attivo, non applica i ruoli dell'interfaccia: il token è una chiave di amministrazione.</li>
  <li>Le modifiche contemporanee allo stesso documento non si sovrascrivono: il secondo utente riceve un avviso.</li>
</ul>

<div class="guida-avviso">Prima di ogni aggiornamento fai un backup e prova il
ripristino su una copia. La guida operativa completa è in
<a href="/guida/aggiornare-gestionale/">Aggiornare il gestionale</a>.</div>
""",
    },
    {
        "slug": "percorso-collaboratore",
        "title": "Percorso Collaboratore: ore e foto dal cantiere",
        "area": "Percorsi per ruolo",
        "roles": SOLO_COLLABORATORE,
        "order": 60,
        "summary": "Cosa vede e cosa fa chi entra solo per rendicontare ore e foto.",
        "body": """
<p>Il ruolo <strong>Collaboratore</strong> è pensato per le partite IVA esterne
(scavi, elettricista, piastrellista, giardiniere…). Con questo ruolo vedi solo
la tua area: <strong>Le mie ore</strong>, <strong>Registra le ore</strong>,
<strong>Foto del cantiere</strong> e <strong>Guida</strong>. Non hai accesso
alle schede clienti, ai prezzi, ai documenti o alle altre sezioni.</p>

<h3>Cosa fai tu</h3>
<ol>
  <li>Entri con le credenziali che ti ha dato l'ufficio.</li>
  <li>Registri le ore lavorate, indicando data, ore, cantiere e lavoro svolto.</li>
  <li>Carichi le foto del cantiere o le bolle di acquisto dal telefono.</li>
  <li>Puoi correggere o cancellare le tue registrazioni finché l'ufficio non le ha controllate.</li>
</ol>

<h3>Cosa non puoi fare</h3>
<ul>
  <li>Vedere i dati dei clienti, i prezzi o i documenti.</li>
  <li>Modificare le ore di altri collaboratori.</li>
  <li>Approvare ferie o permessi (il tuo rapporto è regolato dalla tua fattura).</li>
</ul>

<h3>Come vengono usate le tue ore</h3>
<p>L'ufficio controlla le ore e le foto, le confronta con la tua fattura e le
collega al cantiere. Se una giornata è sbagliata, correggila tu: è più semplice
che farla correggere all'ufficio.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-personale.svg" alt="Percorso dei collaboratori esterni" loading="lazy">
  <figcaption>Dal telefono in cantiere al controllo dell'ufficio, fino alla fattura.</figcaption>
</figure>

<p>La procedura dettagliata è in <a href="/guida/il-mio-lavoro/">Il mio lavoro:
ore e foto dal cantiere</a>.</p>
""",
    },
]
