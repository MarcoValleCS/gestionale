"""Guide delle impostazioni e dell'amministrazione del gestionale."""

from .base import SOLO_ADMIN

PAGINE = [
    {
        "slug": "impostazioni",
        "title": "Impostazioni: la mappa",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 10,
        "summary": "Cosa si configura, in che ordine farlo e quali pagine toccare.",
        "body": """
<p>Le <strong>Impostazioni</strong> sono riservate all'amministratore. Qui si
configura il gestionale: dati aziendali, tabelle di base, utenti, email,
backup e aggiornamenti.</p>

<h3>L'ordine consigliato</h3>
<ol>
  <li><a href="/guida/dati-azienda/">Dati azienda</a>: ragione sociale, P.IVA, PEC, logo, colori e condizioni.</li>
  <li><a href="/guida/tabelle-base/">Tabelle di base</a>: IVA, unità di misura, etichette, pagamenti.</li>
  <li><a href="/guida/numerazioni/">Numerazioni</a>: prefissi e progressivi dei documenti.</li>
  <li><a href="/guida/utenti-ruoli/">Utenti e ruoli</a>: accessi e permessi.</li>
  <li><a href="/guida/email-configurazione/">Email</a>: invio, casella in arrivo e modelli.</li>
  <li><a href="/guida/copia-sicurezza/">Copia di sicurezza</a>: backup e ripristino.</li>
</ol>

<h3>Le pagine delle impostazioni</h3>
<table>
  <thead><tr><th>Pagina</th><th>Cosa contiene</th></tr></thead>
  <tbody>
    <tr><td>Dati azienda</td><td>Anagrafica, logo, colori, condizioni stampate</td></tr>
    <tr><td>Aliquote IVA</td><td>Aliquote, natura SDI, predefinite</td></tr>
    <tr><td>Unità di misura</td><td>PZ, KG, MT, H…</td></tr>
    <tr><td>Etichette</td><td>Etichette colorate di contatti e articoli</td></tr>
    <tr><td>Condizioni di pagamento</td><td>Rimessa diretta, bonifico 30/60…</td></tr>
    <tr><td>Numerazioni</td><td>Prefissi e numeri dei documenti</td></tr>
    <tr><td>Email</td><td>Stato SMTP/IMAP, prova di invio, modelli</td></tr>
    <tr><td>Fasi lead</td><td>Pipeline commerciale</td></tr>
    <tr><td>Registro attività</td><td>Chi ha creato, modificato o cancellato</td></tr>
    <tr><td>Copia di sicurezza</td><td>Backup disponibili da scaricare</td></tr>
  </tbody>
</table>

<div class="guida-avviso">Le modifiche alle impostazioni valgono per tutti gli
utenti. Prima di cambiare numerazioni, condizioni di pagamento o dati fiscali,
avvisa chi emette documenti: i nuovi documenti useranno i valori aggiornati, i
vecchi restano come sono.</div>
""",
    },
    {
        "slug": "dati-azienda",
        "title": "Dati azienda e grafica dei documenti",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 20,
        "summary": "Anagrafica, PEC, regime fiscale, logo, colori, stile di stampa e condizioni.",
        "body": """
<p>In <em>Impostazioni → Dati azienda</em> si compila l'intestazione che compare
sui documenti e si sceglie la grafica di stampe e gestionale.</p>

<h3>Dati fiscali</h3>
<ul>
  <li><strong>Ragione sociale</strong>, partita IVA, codice fiscale, PEC.</li>
  <li><strong>Regime fiscale</strong>: serve alla fatturazione elettronica (es. RF01 ordinario, RF19 forfettario).</li>
  <li><strong>Indirizzo completo</strong>: via, CAP, città, provincia, paese.</li>
  <li><strong>Contatti</strong>: email, telefono, sito web, IBAN.</li>
</ul>
<p>La PEC aziendale va indicata qui. Per la trasmissione allo SDI, però, il
gestionale usa le credenziali <code>EMAIL_*</code> del file <code>.env</code>:
in produzione devono essere quelle della casella PEC. Senza P.IVA, indirizzo e
PEC la fattura elettronica non si genera.</p>

<h3>Logo e colori</h3>
<ul>
  <li><strong>Logo aziendale</strong>: compare in alto nei documenti stampati (PNG o JPG).</li>
  <li><strong>Logo del gestionale</strong>: sostituisce l'icona in alto a sinistra nel menu.</li>
  <li><strong>Colore documenti</strong>: colore di intestazioni e grafica delle stampe.</li>
  <li><strong>Colore del gestionale</strong>: menu, pulsanti e collegamenti.</li>
  <li><strong>Sfondo del gestionale</strong>: azzurro tenue, bianco, grigio, caldo o azzurro.</li>
  <li><strong>Stile dei documenti</strong>: classico, moderno, sobrio o elegante.</li>
</ul>

<h3>Condizioni stampate</h3>
<p><strong>Condizioni generali</strong> (in fondo ai documenti): testo semplice
che compare in calce a preventivi, ordini e fatture. <strong>Condizioni di
vendita</strong>: testo più ampio, usato nei preventivi, negli ordini e nella
pagina pubblica dei termini. Puoi usare i segnaposto <code>{azienda}</code>,
<code>{indirizzo}</code>, <code>{piva}</code>, <code>{email}</code>,
<code>{telefono}</code> e una formattazione semplice (grassetto, elenchi).</p>

<h3>Dopo il salvataggio</h3>
<p>I nuovi documenti usano subito i dati aggiornati. Le stampe già emesse non
cambiano. Se cambi il logo, controlla una stampa di prova per verificare
dimensioni e colori.</p>

<div class="guida-avviso">I dati fiscali sbagliati si propagano a tutte le
fatture elettroniche. Controlla P.IVA, regime fiscale e PEC con il
commercialista prima del primo invio allo SDI.</div>
""",
    },
    {
        "slug": "tabelle-base",
        "title": "Tabelle di base: IVA, unità, etichette, pagamenti",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 30,
        "summary": "Le voci che alimentano le tendine dei documenti e le scadenze.",
        "body": """
<p>Le tabelle di base sono gli elenchi che il gestionale usa nei moduli. Se
manca una voce, non compare nelle tendine.</p>

<h3>Aliquote IVA</h3>
<ul>
  <li><strong>Codice</strong>: 22, 10, 4, 5, N2.2… (è anche il codice usato nello SDI).</li>
  <li><strong>Descrizione</strong>, <strong>aliquota %</strong> e <strong>natura</strong> per le operazioni esenti o non imponibili.</li>
  <li><strong>Predefinita per vendite</strong> e <strong>predefinita per acquisti</strong>: la voce proposta nei nuovi articoli.</li>
  <li><strong>Attiva</strong>: se disattivata non compare più nelle tendine, ma resta nei documenti esistenti.</li>
</ul>
<p>Per un'aliquota a 0% la natura è obbligatoria nella fattura elettronica.</p>

<h3>Unità di misura</h3>
<p>Codice (PZ, KG, MT, H…) e descrizione. L'unità predefinita è quella usata
negli articoli e nelle righe. Se un'unità non serve più, disattivala.</p>

<h3>Etichette</h3>
<p>Etichette colorate per contatti e articoli (es. «Showroom», «Cantiere»,
«Promozione»). Hanno nome, colore e descrizione. Si applicano nelle schede e si
usano come filtro negli elenchi.</p>

<h3>Condizioni di pagamento</h3>
<ul>
  <li><strong>Nome</strong> (es. «Bonifico 30 gg»), <strong>giorni</strong> e <strong>fine mese</strong>.</li>
  <li>La scadenza dei documenti si calcola aggiungendo i giorni alla data del documento.</li>
  <li><strong>Fine mese</strong> è un'indicazione della condizione concordata; non sposta automaticamente la scadenza.</li>
</ul>

<h3>Fasi lead</h3>
<p>Le fasi della pipeline (nome, ordine, colore, esito aperto/vinto/perso). La
spunta <strong>«preventivo creato»</strong> indica la fase in cui portare un
lead quando si crea il preventivo. La guida è in <a href="/guida/lead/">Lead</a>.</p>

<div class="guida-avviso">Non eliminare una voce usata da documenti o articoli:
disattivala. Le voci disattivate non compaiono nelle nuove tendine ma restano
leggibili nello storico.</div>
""",
    },
    {
        "slug": "numerazioni",
        "title": "Numerazioni dei documenti",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 40,
        "summary": "Prefissi, progressivi, zeri iniziali e anno: come non creare buchi o duplicati.",
        "body": """
<p>Ogni tipo di documento ha una <strong>numerazione</strong> propria:
preventivo, ordine cliente, ordine fornitore, DDT, fattura emessa e fattura
ricevuta.</p>

<h3>I campi</h3>
<ul>
  <li><strong>Prefisso</strong>: es. <code>PRE-</code>, <code>OC-</code>, <code>OF-</code>, <code>DDT-</code>, <code>FT-</code>.</li>
  <li><strong>Anno</strong>: se impostato, il numero contiene l'anno; se è <code>0</code>, la numerazione è continua senza anno.</li>
  <li><strong>Prossimo numero</strong>: il numero che verrà usato al prossimo documento.</li>
  <li><strong>Zeri iniziali</strong>: quante cifre deve avere il numero (es. 4 → <code>0001</code>).</li>
</ul>
<p>Esempio: prefisso <code>PRE-</code>, anno 2026, prossimo numero 12, zeri 4
→ <code>PRE-2026-0012</code>.</p>

<h3>Come funziona</h3>
<ul>
  <li>Il numero viene assegnato al <strong>primo salvataggio</strong>: anche una bozza ha già il suo numero.</li>
  <li>Se elimini una bozza, il numero non viene riutilizzato: resta un buco nella sequenza.</li>
  <li>L'incremento è atomico: due utenti che salvano insieme non ottengono lo stesso numero.</li>
  <li>Il numero è unico: il database rifiuta un duplicato.</li>
  <li>Cambiare «Prossimo numero» vale solo per i documenti futuri; i numeri già assegnati non cambiano.</li>
</ul>

<h3>Quando cambiarle</h3>
<ul>
  <li>All'inizio di un nuovo anno, se vuoi ripartire da 1 con l'anno nel numero.</li>
  <li>Quando si passa da un gestionale vecchio e si vuole continuare la numerazione.</li>
  <li>Mai a metà anno senza un motivo fiscale: un buco nella numerazione delle fatture va giustificato.</li>
</ul>

<div class="guida-avviso">Prima di cambiare la numerazione delle fatture,
sentì il commercialista. Un numero saltato o duplicato è un problema fiscale,
non solo un fastidio.</div>
""",
    },
    {
        "slug": "utenti-ruoli",
        "title": "Utenti e ruoli",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 50,
        "summary": "Creare un accesso, assegnare i ruoli, disattivare chi non lavora più.",
        "body": """
<p>Da <em>Utenti</em> si creano e si modificano gli accessi. Ogni utente ha uno
o più <strong>ruoli</strong> (gruppi Django) che decidono cosa vede e cosa può
fare.</p>

<h3>Creare un utente</h3>
<ol>
  <li>Premi <strong>Nuovo utente</strong>.</li>
  <li>Compila nome utente, nome, cognome ed email.</li>
  <li>Scegli almeno un <strong>ruolo</strong>.</li>
  <li>Imposta una password di almeno 10 caratteri e confermala.</li>
  <li>Salva: l'utente è attivo e può accedere.</li>
</ol>

<h3>Modificare un utente</h3>
<ul>
  <li>Cambia nome, email o ruoli.</li>
  <li>Per cambiare la password, compila il campo <strong>Nuova password</strong>; se lo lasci vuoto, la password resta.</li>
  <li>Togli la spunta <strong>Attivo</strong> per bloccare l'accesso senza cancellare lo storico.</li>
</ul>

<h3>I ruoli</h3>
<table>
  <thead><tr><th>Ruolo</th><th>Permessi principali</th></tr></thead>
  <tbody>
    <tr><td>Amministratore</td><td>Tutto: impostazioni, utenti, dati, documenti.</td></tr>
    <tr><td>Vendite</td><td>Contatti, articoli, preventivi, ordini cliente, DDT, fatture emesse, statistiche.</td></tr>
    <tr><td>Acquisti</td><td>Contatti, articoli, ordini fornitore, listini, fatture ricevute.</td></tr>
    <tr><td>Magazzino</td><td>Giacenze, movimenti, rettifiche, ricezione merci, DDT, consegne.</td></tr>
    <tr><td>Personale</td><td>Dipendenti, ore, ferie e permessi, presenze, collaboratori.</td></tr>
    <tr><td>Collaboratore</td><td>Solo la propria area: ore e foto del cantiere.</td></tr>
  </tbody>
</table>

<h3>Regole importanti</h3>
<ul>
  <li>Un utente con <strong>solo</strong> il ruolo Collaboratore viene reindirizzato sempre alla sua area.</li>
  <li>Se un collaboratore deve vedere anche altro, aggiungi un secondo ruolo.</li>
  <li>Il superuser (amministratore Django) bypassa i ruoli: usalo solo per la manutenzione.</li>
  <li>L'email dell'utente diventa il <strong>Reply-To</strong> delle email che invia: il mittente resta la casella aziendale.</li>
</ul>

<div class="guida-avviso">Prima di disattivare un utente, controlla se è
collegato a un dipendente o a un collaboratore. La disattivazione blocca
l'accesso ma non cancella le registrazioni fatte.</div>
""",
    },
    {
        "slug": "email-configurazione",
        "title": "Email: invio, casella e modelli",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 60,
        "summary": "Configurare SMTP e IMAP, provare l'invio, personalizzare i testi e capire la coda.",
        "body": """
<p>Il gestionale invia preventivi, ordini fornitore, fatture e solleciti per
email, e può leggere la casella aziendale via IMAP. La configurazione sta nel
file <code>.env</code> del server, non nell'interfaccia.</p>

<h3>Invio (SMTP)</h3>
<pre>EMAIL_HOST=smtp.tuoprovider.it
EMAIL_PORT=587
EMAIL_HOST_USER=info@tuodominio.it
EMAIL_HOST_PASSWORD=la-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=Nome Azienda &lt;info@tuodominio.it&gt;</pre>
<p>Per la fatturazione elettronica servono le credenziali della casella
<strong>PEC</strong>: l'XML viene trasmesso allo SDI via PEC.</p>
<p>Dopo la modifica riavvia il servizio: <code>docker compose up -d</code> in
produzione, oppure riavvia <code>runserver</code> in locale.</p>

<h3>Casella in arrivo (IMAP)</h3>
<pre>IMAP_HOST=imaps.aruba.it
IMAP_PORT=993
IMAP_USER=info@tuodominio.it
IMAP_PASSWORD=la-password
IMAP_FOLDER=INBOX</pre>
<p>Se non indichi utente e password IMAP, il gestionale usa le stesse
credenziali dell'invio. La casella può essere scaricata periodicamente da un
comando schedulato sul server; il pulsante <strong>Scarica nuove email</strong>
forza comunque il controllo.</p>

<h3>Prova di invio</h3>
<p>In <em>Impostazioni → Email</em> vedi host, porta, utente e mittente
configurati. Scrivi un indirizzo e premi <strong>Invia prova</strong>: se
arriva, la configurazione funziona. Se non arriva, controlla spam, credenziali
e porta/TLS.</p>

<h3>Modelli delle email</h3>
<p>In <em>Impostazioni → Modelli email</em> puoi cambiare oggetto e testo di:</p>
<ul>
  <li>invio preventivo;</li>
  <li>invio fattura;</li>
  <li>sollecito preventivo;</li>
  <li>sollecito fattura;</li>
  <li>invio ordine fornitore.</li>
</ul>
<p>I segnaposto disponibili sono <code>{cliente}</code>, <code>{numero}</code>,
<code>{data}</code>, <code>{totale}</code>, <code>{scadenza}</code>,
<code>{giorni}</code>, <code>{ritardo}</code>, <code>{cantiere}</code>,
<code>{riferimento}</code>, <code>{azienda}</code>, <code>{validita}</code> e
<code>{termini}</code>.</p>

<h3>La coda</h3>
<p>Le email non partono durante il clic: vengono messe in coda e spedite da un
comando in background, di norma ogni pochi minuti. Così un server di posta
lento non blocca la pagina. Se la coda si blocca, controlla che il comando
<code>invia_coda_email</code> sia schedulato e leggi i suoi log.</p>

<div class="guida-avviso">Non mettere la password SMTP o PEC in un documento,
in un messaggio o nella guida. Se sospetti che sia stata esposta, cambiala e
aggiorna il <code>.env</code>.</div>
""",
    },
    {
        "slug": "registro-attivita",
        "title": "Registro attività",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 70,
        "summary": "Chi ha creato, modificato o cancellato documenti, articoli e contatti.",
        "body": """
<p>Il <strong>Registro attività</strong> tiene traccia delle operazioni fatte nel
gestionale: creazione, modifica e cancellazione di documenti, articoli,
contatti e altre entità sorvegliate.</p>

<h3>Cosa mostra</h3>
<ul>
  <li><strong>Quando</strong>: data e ora dell'operazione.</li>
  <li><strong>Utente</strong>: chi ha fatto l'operazione (se disponibile).</li>
  <li><strong>Azione</strong>: creato, modificato, cancellato.</li>
  <li><strong>Tipo</strong>: modello interessato (preventivo, fattura, articolo…).</li>
  <li><strong>Oggetto</strong> e <strong>dettagli</strong>: cosa è cambiato.</li>
</ul>

<h3>Filtri</h3>
<p>Puoi filtrare per utente, tipo e azione. La pagina mostra gli ultimi 300
movimenti: per lo storico più vecchio usa i filtri o l'amministrazione Django.</p>

<h3>Quando usarlo</h3>
<ul>
  <li>Un documento è cambiato e non sai chi lo ha modificato.</li>
  <li>Un articolo o un prezzo è stato cancellato.</li>
  <li>Vuoi verificare l'attività di un collaboratore o di un utente.</li>
  <li>Stai indagando su un errore o un accesso sospetto.</li>
</ul>

<div class="guida-avviso">Il registro è una traccia, non una copia di
sicurezza: non permette di ripristinare un documento cancellato. Per quello
servono i backup.</div>
""",
    },
    {
        "slug": "copia-sicurezza",
        "title": "Copia di sicurezza (backup)",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 80,
        "summary": "Dove sono i backup, come scaricarli, come ripristinare e cosa controllare.",
        "body": """
<p>Ogni notte il gestionale salva una copia del database e dei file caricati.
Le copie restano sul server nella cartella configurata da
<code>BACKUP_ROOT</code> (in produzione di norma <code>/opt/backups/gestionale</code>).</p>

<h3>Dove sono</h3>
<p>In <em>Impostazioni → Copia di sicurezza</em> vedi l'elenco delle copie
disponibili, con data, dimensione e tipo (database o file). Restano sul server
14 giorni, poi le più vecchie vengono cancellate.</p>

<h3>Scaricare una copia</h3>
<ol>
  <li>Apri la pagina della copia di sicurezza.</li>
  <li>Premi <strong>Scarica</strong> accanto al file.</li>
  <li>Salva il file su un computer o su un disco esterno.</li>
</ol>
<p>È importante farlo ogni tanto: se il server si guasta, le copie sul server
andrebbero perse.</p>

<h3>Avvisi automatici</h3>
<p>Il gestionale manda un'email se il backup fallisce, se il disco del server si
riempie o se il sito non risponde. Se ricevi un avviso, c'è qualcosa da
controllare.</p>

<h3>Ripristinare una copia</h3>
<p>Il ripristino si fa sul server, con lo script <code>scripts/restore.sh</code>:</p>
<pre>./scripts/restore.sh /opt/backups/gestionale/db_2026-10-03_0300.sql.gz</pre>
<p>Lo script chiede conferma e salva prima una copia dello stato attuale. Prima
di ripristinare, fai una copia di quello che c'è adesso.</p>

<h3>Controlli periodici</h3>
<ul>
  <li>La copia più recente è di ieri notte?</li>
  <li>Il file del database ha una dimensione plausibile?</li>
  <li>Hai scaricato una copia fuori dal server negli ultimi 30 giorni?</li>
  <li>Hai mai provato un ripristino su una copia di prova?</li>
</ul>

<div class="guida-avviso">Un backup mai provato non è un backup affidabile.
Almeno una volta all'anno prova il ripristino su un ambiente di prova, non sul
server di produzione.</div>
""",
    },
    {
        "slug": "aggiornare-gestionale",
        "title": "Aggiornare il gestionale",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 90,
        "summary": "Controllare la versione, fare il backup, aggiornare codice e container, verificare.",
        "body": """
<p>Il gestionale si aggiorna dal repository Git. La produzione gira in Docker
con PostgreSQL; in locale si può usare SQLite. Prima di ogni aggiornamento:
backup e verifica della versione.</p>

<h3>Controllare la versione</h3>
<p>In produzione, entra nella cartella del progetto e leggi l'ultimo commit:</p>
<pre>cd /opt/gestionale
git log -1 --oneline
git fetch origin
git status</pre>
<p>Se il repository locale è indietro, <code>git status</code> lo dice. Per
vedere i commit mancanti: <code>git log HEAD..origin/main --oneline</code>.</p>

<h3>Prima di aggiornare</h3>
<ol>
  <li>Fai un <strong>backup</strong> del database e dei file:
  <code>./scripts/backup.sh</code>.</li>
  <li>Scarica una copia del backup sul tuo computer.</li>
  <li>Avvisa gli utenti: durante l'aggiornamento il sito può essere irraggiungibile per qualche minuto.</li>
  <li>Leggi le modifiche: se ci sono nuove migrazioni, verranno applicate all'avvio.</li>
</ol>

<h3>Aggiornare</h3>
<pre>cd /opt/gestionale
git pull
docker compose --profile mcp up -d --build</pre>
<p>Il profilo <code>mcp</code> serve a ricostruire anche il server MCP, se è
attivo. Senza, il container MCP continuerebbe a girare con il codice vecchio.</p>
<p>All'avvio il container <code>web</code> applica le migrazioni, raccoglie gli
statici e crea l'utente amministratore se configurato. Controlla i log:</p>
<pre>docker compose ps
docker compose logs -f web</pre>

<h3>Dopo l'aggiornamento</h3>
<ul>
  <li>Apri il gestionale e fai login.</li>
  <li>Controlla la dashboard e una pagina per ogni area.</li>
  <li>Verifica che le guide siano aggiornate (le pagine del programma si aggiornano al riavvio, tranne quelle modificate a mano).</li>
  <li>Se qualcosa non funziona, ripristina il backup e segnala l'errore.</li>
</ul>

<h3>Aggiornare la guida</h3>
<p>Le pagine scritte nel codice si caricano con:</p>
<pre>docker compose exec web python manage.py carica_guida</pre>
<p>Il comando crea le pagine mancanti e aggiorna quelle del programma non
modificate dall'interfaccia. Con <code>--aggiorna</code> sovrascrive anche le
pagine modificate a mano: usalo solo se sei sicuro.</p>

<div class="guida-avviso">Non aggiornare senza backup. Se l'aggiornamento
introduce una migrazione problematica, il ripristino del database è l'unico
modo rapido per tornare operativi.</div>
""",
    },
    {
        "slug": "assistente-mcp",
        "title": "Assistente MCP: accesso da un'intelligenza artificiale",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 100,
        "summary": "Cosa può fare un client MCP, come proteggerlo e perché il token è una chiave di amministrazione.",
        "body": """
<p>Il <strong>server MCP</strong> espone il gestionale a un assistente AI (Claude
Desktop, un client MCP, un agente interno). Può leggere e scrivere dati tramite
strumenti dedicati, riusando i servizi dell'applicazione.</p>

<h3>Due trasporti</h3>
<ul>
  <li><strong>stdio</strong>: locale, senza porte di rete. Si avvia con
  <code>python scripts/mcp_server.py</code> e si configura nel client.</li>
  <li><strong>HTTP</strong>: in produzione, dietro Caddy, all'indirizzo
  <code>https://&lt;dominio&gt;/mcp</code>. Richiede un token Bearer.</li>
</ul>

<h3>Attivare la produzione</h3>
<pre># 1. Genera un token
openssl rand -hex 32

# 2. Nel .env
MCP_ENABLED=true
MCP_TOKEN=il-token-generato
MCP_USER=admin

# 3. Avvia il servizio
docker compose --profile mcp up -d
docker compose logs -f mcp</pre>
<p>Il servizio non pubblica porte: l'unico ingresso è Caddy. Ogni richiesta
deve avere <code>Authorization: Bearer &lt;token&gt;</code>.</p>

<h3>Cosa protegge il server</h3>
<ul>
  <li>Token Bearer confrontato a tempo costante.</li>
  <li>Allowlist di IP (<code>MCP_ALLOWED_IPS</code>), se configurata.</li>
  <li>Limite di richieste al minuto per token (<code>MCP_RATE_LIMIT</code>).</li>
  <li>Protezione DNS rebinding: solo gli host dichiarati sono ammessi.</li>
  <li>Log di ogni chiamata: chi, quale strumento, quanto tempo.</li>
</ul>

<h3>La regola più importante</h3>
<p>Il server MCP <strong>non applica i ruoli dell'interfaccia</strong>: chi ha il
token può fare tutto quello che può fare l'amministratore, compresi i dati che
un collaboratore non vedrebbe. Il token va trattato come una chiave di
amministrazione: personale, non condiviso, non salvato in un documento.</p>
<p>Con più utenti si possono usare token diversi (<code>MCP_TOKENS</code>),
anche limitati alle sole letture con lo scope <code>mcp:sola-lettura</code>.</p>

<h3>Verifica rapida</h3>
<pre># Senza token: deve rispondere 401
curl -s -o /dev/null -w "%{http_code}\\n" https://tuodominio/mcp</pre>
<p>Con il token, il client risponde all'inizializzazione e mostra gli strumenti
disponibili. Se risponde 401, il token è sbagliato o manca l'intestazione.</p>

<div class="guida-avviso">Se sospetti che il token sia stato esposto,
rigeneralo, aggiorna il <code>.env</code> e riavvia il servizio MCP. Non
riutilizzare lo stesso token per più persone.</div>
""",
    },
    {
        "slug": "guida-personalizzata",
        "title": "Scrivere e personalizzare la guida",
        "area": "Impostazioni",
        "roles": SOLO_ADMIN,
        "order": 110,
        "summary": "Creare una pagina, scegliere i ruoli, usare titoli, immagini e diagrammi.",
        "body": """
<p>La guida è una wiki interna: le pagine si possono creare e modificare dal
gestionale, con una formattazione semplice. Ogni pagina può essere visibile a
tutti o solo ad alcuni ruoli.</p>

<h3>Creare una pagina</h3>
<ol>
  <li>Apri <strong>Guida</strong> e premi <strong>Nuova pagina</strong> (solo amministratore).</li>
  <li>Compila titolo, sommario, sezione e contenuto.</li>
  <li>In <strong>Ruoli che possono leggerla</strong> scrivi i nomi separati da
  virgola (es. <code>Vendite, Amministratore</code>). Vuoto = tutti.</li>
  <li>Decidi l'ordine nella sezione e se la pagina è pubblicata.</li>
  <li>Salva.</li>
</ol>

<h3>Cosa accetta il contenuto</h3>
<ul>
  <li>Titoli <code>h2</code>, <code>h3</code>, <code>h4</code>.</li>
  <li>Paragrafi, grassetto, corsivo, elenchi puntati e numerati.</li>
  <li>Tabelle, link, blocchi di codice e citazioni.</li>
  <li>Immagini locali della guida: <code>&lt;img src="/static/img/guida/nome.svg"&gt;</code>.</li>
  <li>Classi CSS per gli avvisi: <code>guida-avviso</code>, <code>guida-suggerimento</code>, <code>guida-ruolo</code>, <code>guida-passi</code>.</li>
</ul>
<p>Script, iframe e immagini esterne vengono rimossi al salvataggio: è una
protezione, non un errore.</p>

<h3>Le immagini e i diagrammi</h3>
<p>I diagrammi dei processi sono file SVG in
<code>static/img/guida/</code>. Puoi aggiungerne uno nuovo caricandolo sul
server e richiamandolo con un percorso che inizia per
<code>/static/img/guida/</code>. Le immagini esterne non sono ammesse.</p>

<h3>Pagine del programma e modifiche</h3>
<p>Le pagine scritte nel codice si caricano con
<code>python manage.py carica_guida</code>. Il comando:</p>
<ul>
  <li>crea le pagine mancanti;</li>
  <li>aggiorna le pagine del programma non ancora modificate dall'interfaccia;</li>
  <li>lascia intatte le pagine modificate a mano (o le sovrascrive con <code>--aggiorna</code>).</li>
</ul>

<h3>Buone regole</h3>
<ul>
  <li>Una pagina = un processo o una funzione, non un elenco infinito.</li>
  <li>Metti i passaggi in ordine numerato e i pulsanti tra virgolette.</li>
  <li>Assegna i ruoli giusti: chi non può usare una funzione non deve vedere la pagina.</li>
  <li>Quando cambi un processo, aggiorna la pagina: una guida vecchia è peggio di nessuna guida.</li>
</ul>
""",
    },
]
