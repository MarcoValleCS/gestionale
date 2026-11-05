"""Guide del personale: dipendenti, ore, ferie, presenze, collaboratori."""

from .base import SOLO_PERSONALE

PAGINE = [
    {
        "slug": "personale",
        "title": "Personale: dipendenti, ore e assenze",
        "area": "Personale",
        "roles": SOLO_PERSONALE,
        "order": 10,
        "summary": "Anagrafica dipendenti, contratto, registrazione ore, ferie e permessi, presenze.",
        "body": """
<p>La sezione <strong>Personale</strong> gestisce dipendenti, ore lavorate,
ferie e permessi, registro presenze e collaboratori esterni.</p>

<figure>
  <img class="guida-immagine" src="/static/img/guida/flusso-personale.svg" alt="Flusso del personale" loading="lazy">
  <figcaption>Da una parte i dipendenti, dall'altra i collaboratori esterni; entrambi passano dal cantiere.</figcaption>
</figure>

<h3>La scheda dipendente</h3>
<ul>
  <li><strong>Dati anagrafici</strong>: nome, cognome, codice fiscale, email, telefono.</li>
  <li><strong>Mansione</strong> e eventuale <strong>utente collegato</strong>.</li>
  <li><strong>Contratto</strong>: data assunzione, cessazione, ore settimanali, costo orario.</li>
  <li><strong>Ferie annue</strong> (giorni) e <strong>permessi annui</strong> (ore).</li>
  <li><strong>Stato</strong>: attivo o cessato.</li>
</ul>

<h3>Le tre registrazioni delle ore</h3>
<ol>
  <li><strong>Singola</strong>: una giornata per un dipendente, con cantiere e descrizione.</li>
  <li><strong>Ore del giorno</strong>: tutta la squadra in una volta, sulla stessa giornata e attività.</li>
  <li><strong>Ore standard</strong>: un periodo di giornate lavorative con lo stesso orario (es. 8 ore dal lunedì al venerdì).</li>
</ol>
<p>La guida dettagliata è in <a href="/guida/registrare-ore/">Registrare le ore</a>.</p>

<h3>Ferie e permessi</h3>
<p>Le richieste si registrano con tipo (ferie, permessi ROL, malattia, non
retribuito, altro), dal/al e stato. Le richieste approvate entrano nel calcolo
dei residui e nel registro presenze. La guida è in
<a href="/guida/ferie-permessi/">Ferie e permessi</a>.</p>

<h3>Registro presenze</h3>
<p>Il <strong>Registro presenze</strong> mostra mese per mese, per ogni
dipendente, le ore registrate e le assenze approvate. Le sigle sono F (ferie),
P (permessi), M (malattia), N (non retribuito), A (altro). La guida è in
<a href="/guida/presenze/">Registro presenze</a>.</p>

<h3>Collaboratori esterni</h3>
<p>I collaboratori sono le partite IVA esterne. Hanno un'anagrafica propria,
possono avere un utente collegato per registrare ore e foto dal telefono, e le
loro ore si confrontano con le fatture ricevute. La guida è in
<a href="/guida/collaboratori/">Collaboratori esterni</a>.</p>

<div class="guida-avviso">Il costo orario e le ore sono dati per il controllo
interno, non sostituiscono il libro paga o il consulente del lavoro. Le ferie e
i permessi residui sono calcolati sulle richieste approvate, non su quelle in
attesa.</div>
""",
    },
    {
        "slug": "registrare-ore",
        "title": "Registrare le ore",
        "area": "Personale",
        "roles": SOLO_PERSONALE,
        "order": 20,
        "summary": "Inserimento singolo, rapido di squadra e ore standard: quando usare ciascuno.",
        "body": """
<p>Le ore si registrano in <em>Personale → Registrazione ore</em>. Le ore vanno
in quarti d'ora: <code>7,5</code> significa 7 ore e 30 minuti.</p>

<h3>Registrazione singola</h3>
<ol>
  <li>Premi <strong>Nuova registrazione</strong>.</li>
  <li>Scegli dipendente, data, ore e tipo (ordinario, straordinario, trasferta).</li>
  <li>Indica il cantiere, la descrizione dell'attività e se è addebitabile al cliente.</li>
  <li>Salva: le ore entrano nei totali del dipendente e del cantiere.</li>
</ol>

<h3>Ore del giorno (tutta la squadra)</h3>
<ol>
  <li>Premi <strong>Ore del giorno</strong>.</li>
  <li>Scegli giornata, tipo, cantiere e descrizione comune.</li>
  <li>Scrivi le ore accanto a ogni dipendente; lascia vuoto chi non ha lavorato.</li>
  <li>Premi <strong>Salva giornata</strong>.</li>
</ol>
<p>Se per un dipendente esiste già una registrazione dello stesso tipo in quella
data, viene aggiornata invece di crearne una seconda.</p>

<h3>Ore standard</h3>
<ol>
  <li>Premi <strong>Ore standard</strong>.</li>
  <li>Scegli dipendente, periodo, ore al giorno, tipo, cantiere e descrizione.</li>
  <li>Se serve, includi il sabato.</li>
  <li>Decidi se sovrascrivere le giornate già registrate.</li>
  <li>Salva: vengono create solo le giornate dal lunedì al venerdì (più il sabato se scelto).</li>
</ol>
<p>È la scelta giusta per chi lavora sempre lo stesso orario. Se una giornata
ha già una registrazione e non hai scelto «Sovrascrivi», viene lasciata com'è.</p>

<h3>Regole e controlli</h3>
<ul>
  <li>Minimo 0,25 ore (un quarto d'ora), massimo 24 ore in un giorno.</li>
  <li>Le ore di più registrazioni nello stesso giorno si sommano nel registro presenze.</li>
  <li>Il cantiere è facoltativo, ma senza cantiere le ore non vengono attribuite a un lavoro.</li>
  <li>La descrizione aiuta a capire cosa è stato fatto e a confrontare le fatture dei collaboratori.</li>
</ul>

<h3>Correggere un errore</h3>
<p>Dalla lista delle registrazioni premi la matita, correggi ore, cantiere o
descrizione e salva. Se la registrazione non serve, eliminala. Le modifiche
sono tracciate nel registro attività.</p>

<div class="guida-avviso">Le ore standard creano molte registrazioni in una
volta: controlla il periodo e l'opzione di sovrascrittura prima di salvare. Un
periodo sbagliato è più lungo da correggere che da inserire.</div>
""",
    },
    {
        "slug": "ferie-permessi",
        "title": "Ferie e permessi",
        "area": "Personale",
        "roles": SOLO_PERSONALE,
        "order": 30,
        "summary": "Registrare una richiesta, approvarla o rifiutarla e leggere i residui.",
        "body": """
<p><em>Personale → Ferie e permessi</em> raccoglie le assenze dei dipendenti:
ferie, permessi ROL, malattia, non retribuito e altro.</p>

<h3>Registrare una richiesta</h3>
<ol>
  <li>Premi <strong>Nuova assenza</strong>.</li>
  <li>Scegli il dipendente e il tipo.</li>
  <li>Indica la data di inizio e di fine. Per un solo giorno, usa la stessa data.</li>
  <li>Per un permesso di poche ore nello stesso giorno, compila <strong>Ore</strong>;
  altrimenti lascia vuoto.</li>
  <li>Scrivi il motivo e salva: la richiesta nasce in stato <strong>Richiesta</strong>.</li>
</ol>

<h3>Approvare o rifiutare</h3>
<ol>
  <li>Apri l'elenco e filtra per stato «Richiesta» (o usa il badge «Da approvare»).</li>
  <li>Premi la spunta per approvare o la X per rifiutare.</li>
  <li>La richiesta approvata entra nei residui e nel registro presenze; quella
  rifiutata resta nello storico ma non conta.</li>
</ol>

<h3>Residui</h3>
<p>La scheda dipendente mostra:</p>
<ul>
  <li><strong>Ferie residue</strong>: ferie annue meno i giorni di ferie approvati nell'anno.</li>
  <li><strong>Permessi residui (ROL)</strong>: ore annue meno le ore di permesso approvate nell'anno.</li>
  <li><strong>Ferie godute</strong>, <strong>permessi goduti</strong> e <strong>malattia</strong>.</li>
</ul>
<p>I giorni di ferie si contano sui giorni lavorativi (lunedì-venerdì) nel
periodo richiesto, non sui giorni di calendario.</p>

<h3>Nel registro presenze</h3>
<p>Le assenze approvate compaiono con una sigla: <strong>F</strong> ferie,
<strong>P</strong> permessi, <strong>M</strong> malattia, <strong>N</strong> non
retribuito, <strong>A</strong> altro. Se una giornata ha sia ore sia assenza,
il registro mostra l'assenza.</p>

<div class="guida-avviso">Modifica una richiesta prima di approvarla se le date
o le ore sono sbagliate. Un'assenza approvata per errore va corretta o
annullata, altrimenti i residui restano sbagliati.</div>
""",
    },
    {
        "slug": "presenze",
        "title": "Registro presenze",
        "area": "Personale",
        "roles": SOLO_PERSONALE,
        "order": 40,
        "summary": "Leggere il mese, le sigle delle assenze e i totali per dipendente.",
        "body": """
<p>Il <strong>Registro presenze</strong> mostra un mese alla volta, con una riga
per dipendente attivo e una colonna per ogni giorno. È il controllo rapido di
ore e assenze.</p>

<h3>Come si legge</h3>
<ul>
  <li>Ogni cella contiene le <strong>ore registrate</strong> quel giorno, sommate se ci sono più registrazioni.</li>
  <li>Le assenze approvate compaiono con una sigla: F, P, M, N, A.</li>
  <li>I fine settimana sono evidenziati in grigio.</li>
  <li>L'ultima colonna è il <strong>totale del mese</strong> per dipendente.</li>
  <li>In alto c'è il totale di tutte le ore del mese.</li>
</ul>

<h3>Cambiare mese</h3>
<p>Usa i menu mese/anno o i pulsanti «Mese prec.» e «Mese succ.». Il registro
mostra solo i dipendenti attivi: un dipendente cessato non compare.</p>

<h3>Cosa controllare</h3>
<ol>
  <li>Le giornate senza ore e senza assenza: sono assenze non registrate o giorni non lavorati?</li>
  <li>Le ore totali rispetto alle ore di contratto: ci sono straordinari o difetti?</li>
  <li>Le assenze approvate: corrispondono a quelle richieste?</li>
  <li>I cantieri: le ore sono state registrate sul lavoro giusto?</li>
</ol>

<h3>Correzioni</h3>
<p>Il registro non si modifica direttamente: le ore si correggono da
<a href="/guida/registrare-ore/">Registrazione ore</a>, le assenze da
<a href="/guida/ferie-permessi/">Ferie e permessi</a>. Dopo la correzione,
ricarica il registro.</p>

<div class="guida-suggerimento">Stampa o salva il registro a fine mese: è un
promemoria utile per il consulente del lavoro e per confrontare le ore dei
collaboratori con le fatture.</div>
""",
    },
    {
        "slug": "collaboratori",
        "title": "Collaboratori esterni",
        "area": "Personale",
        "roles": SOLO_PERSONALE,
        "order": 50,
        "summary": "Anagrafica, accesso al gestionale, ore e foto dal cantiere, resoconto per la fatturazione.",
        "body": """
<p>I <strong>collaboratori</strong> sono le partite IVA esterne (scavi,
elettricista, piastrellista, giardiniere…). Hanno un'anagrafica propria e, se
collegati a un utente, possono registrare ore e caricare foto dal telefono.</p>

<h3>Creare un collaboratore</h3>
<ol>
  <li><em>Personale → Collaboratori → Nuovo</em>.</li>
  <li>Indica nome, ditta/attività, specializzazione, codice fiscale o P.IVA, telefono ed email.</li>
  <li>Indica la <strong>tariffa oraria</strong> e l'eventuale <strong>contatto</strong> collegato in anagrafica.</li>
  <li>Se deve accedere al gestionale, scegli l'<strong>utente</strong> collegato.</li>
  <li>Salva: il codice viene generato automaticamente.</li>
</ol>

<h3>Creare l'utente del collaboratore</h3>
<p>L'utente si crea da <em>Utenti</em> (solo Amministratore) e va inserito nel
gruppo <strong>Collaboratore</strong>. Poi, nella scheda del collaboratore,
scegli quell'utente nel campo <strong>Utente</strong>. Senza collegamento, il
collaboratore non vede la sua area: il gestionale mostra una pagina che spiega
di chiedere all'ufficio.</p>
<div class="guida-avviso">Un utente con <strong>solo</strong> il gruppo
Collaboratore viene reindirizzato sempre alla sua area: non vede clienti,
prezzi, documenti o altre sezioni. Se deve vedere altro, va aggiunto anche un
altro ruolo.</div>

<h3>Cosa fa il collaboratore dal telefono</h3>
<ul>
  <li>Registra le <strong>ore</strong> indicando data, ore, cantiere e lavoro svolto.</li>
  <li>Carica <strong>foto del cantiere</strong> o <strong>bolle di acquisto</strong>.</li>
  <li>Può correggere o cancellare solo le proprie registrazioni e le proprie foto.</li>
</ul>

<h3>Controllare le ore e le foto</h3>
<ol>
  <li>Apri <em>Personale → Collaboratori → Ore registrate</em>.</li>
  <li>Filtra per collaboratore, cantiere e mese.</li>
  <li>Controlla il totale del periodo e confrontalo con la fattura ricevuta.</li>
  <li>Le foto e le bolle sono in <a href="/guida/foto-bolle/">Foto e bolle</a>.</li>
</ol>

<h3>Resoconto per la fatturazione</h3>
<p>La pagina <strong>Ore dei collaboratori</strong> raccoglie tutte le ore
registrate, con i filtri per collaboratore, cantiere e mese e il totale del
periodo. Serve a controllare le fatture che arrivano, confrontandole con le ore
effettivamente lavorate.</p>

<div class="guida-avviso">Il collaboratore non approva ferie o permessi e non
vede le ore degli altri. Il rapporto di lavoro e la fattura restano fuori dal
gestionale: qui si tracciano solo ore, foto e costi.</div>
""",
    },
]
