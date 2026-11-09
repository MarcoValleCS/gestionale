# Sicurezza, prestazioni e copie di sicurezza

Note pratiche per chi gestisce il server del gestionale. Non serve leggerle per
usare il programma: servono quando si mette mano al server.

## Copie di sicurezza

Ogni notte alle 3:00 il server salva:

- `db_AAAA-MM-GG_HHMM.sql.gz` — tutto il database (contatti, documenti, ore…)
- `media_AAAA-MM-GG_HHMM.tar.gz` — i file caricati (logo, foto, allegati)

Restano in `/opt/backups/gestionale` per 14 giorni, poi vengono cancellate le
più vecchie. I file sono leggibili solo da `root` (contengono tutti i dati) e
vengono controllati subito dopo la creazione (`gzip -t`): un archivio rovinato
fa partire l'avviso email.

**Le copie sono sullo stesso server.** Se il disco si guasta, si perdono anche
le copie. Per questo:

1. nel gestionale, in *Impostazioni → Copia di sicurezza*, si vedono le copie
   disponibili e si possono **scaricare** su un computer (o su un disco esterno):
   va fatto ogni tanto, ad esempio una volta al mese;
2. si può attivare la copia automatica via email: basta mettere nel file
   `/opt/gestionale/.env` la riga
   `BACKUP_EMAIL=indirizzo@example.com` e riavviare
   (`docker compose up -d`). Ogni notte la copia del database arriva come
   allegato: è una copia che sta fuori dal server.

### Ripristinare una copia

```bash
cd /opt/gestionale
./scripts/restore.sh /opt/backups/gestionale/db_2026-10-03_0300.sql.gz
```

Lo script avvisa che i dati attuali vengono sostituiti e chiede conferma, poi:

1. controlla che il file non sia rovinato (prima di toccare qualsiasi cosa);
2. salva lo stato attuale in `pre-restore_….sql.gz`, accanto al file scelto;
3. ferma il gestionale (e il server MCP) così nessuno scrive durante il ripristino;
4. svuota e ricarica il database **in un'unica transazione**: se il file dà
   errore a metà, il database resta esattamente com'era;
5. riavvia il gestionale (anche se qualcosa è andato storto).

## Avvisi automatici

Il gestionale manda una email (a `info@aquaforma.it`, o all'indirizzo indicato
nella variabile `AVVISO_EMAIL` del `.env`) quando:

- il backup notturno non riesce;
- il disco del server è pieno all'85% o più;
- il sito non risponde per tre controlli di fila (controllo ogni 5 minuti);
- il sito torna raggiungibile dopo un guasto.

Sono avvisi brevi: se ne arriva uno, c'è qualcosa da guardare sul server.

## Cosa protegge il gestionale

- **Accesso**: tutto richiede il login; ogni area ha i suoi ruoli (Vendite,
  Acquisti, Magazzino, Personale, Collaboratore, Amministratore).
- **Tentativi di accesso**: dopo 8 tentativi sbagliati in 5 minuti lo stesso
  indirizzo viene bloccato per qualche minuto.
- **File caricati**: i tipi di file che il browser può eseguire (HTML, SVG,
  eseguibili…) vengono rifiutati; i file si scaricano invece di aprirsi dentro
  la pagina.
- **Password**: minimo 10 caratteri, non troppo comuni, non tutte numeriche,
  non uguali al nome utente.
- **Log del server**: non contengono password né dati dei documenti; le pagine
  non trovate non vengono registrate (l'indirizzo può contenere il testo di una
  ricerca).
- **Collegamento cifrato**: HTTPS obbligatorio, cookie di sessione solo su
  HTTPS, HSTS attivo.
- **Content-Security-Policy**: le pagine caricano solo risorse del gestionale
  (niente CDN esterni) e nessun oggetto incorporato da altri siti.
- **Azioni solo da modulo**: emettere, confermare, consegnare, convertire,
  duplicare, disattivare… funzionano solo con un invio di modulo (POST con
  token CSRF). Un link o un'immagine (anche dentro un'email letta nel
  gestionale) non può far partire nulla.
- **Email ricevute**: l'HTML del messaggio viene ripulito. Restano grafica e
  link completi (`https://…`, `mailto:`), ma spariscono script, indirizzi
  relativi verso le pagine del gestionale, stili che caricano indirizzi
  (`url(…)`) e le classi della pagina (con cui un'email poteva coprire lo
  schermo con un finto avviso).
- **Collaboratori esterni**: oltre alle pagine, anche i file caricati sono
  limitati: scaricano solo le proprie foto/bolle e il logo.
- **Doppio clic e utenti contemporanei**: emissione DDT, consegna, conferma
  ordine, conversione preventivo, fatturazione da DDT e ricezione merce
  cambiano stato con un solo `UPDATE … WHERE stato = …`: se due richieste
  arrivano insieme, la seconda viene rifiutata e il magazzino si muove una volta
  sola. In più, dopo l'invio i pulsanti dei moduli si disattivano per qualche
  secondo.
- **PDF**: WeasyPrint non scarica nulla (né `http://` né `file://`): il
  documento è già completo, logo compreso.
- **Utenti**: le password scelte dall'amministratore seguono le stesse regole
  del cambio password (lunghezza, password comuni, solo numeri). Chi ha il
  ruolo «Amministratore» ma non è superutente non può modificare un superutente.

## Il server MCP (assistenti AI)

Se in produzione è attivo il server MCP (`MCP_ENABLED=true`), l'indirizzo
`https://<dominio>/mcp` è una **seconda porta d'accesso** ai dati, separata
dall'interfaccia. Protezioni attive:

- **Token Bearer** su ogni richiesta (intestazione `Authorization`), confrontato
  a tempo costante: senza token non passa nulla e la risposta è 401.
- **Nessuna porta pubblicata**: il contenitore del server MCP è raggiungibile
  solo dalla rete interna di Docker, l'unico ingresso è Caddy con HTTPS.
- **Allowlist degli IP** (facoltativa, `MCP_ALLOWED_IPS`).
- **Limite di richieste** al minuto per token (`MCP_RATE_LIMIT`, 300 per
  default): se si superano, la risposta è 429.
- **Protezione DNS rebinding**: il server accetta richieste solo dagli host
  dichiarati (`MCP_ALLOWED_HOSTS`, per default il dominio del gestionale).
- **Registro delle chiamate**: ogni uso di uno strumento finisce nel log
  (`docker compose logs mcp`) con utente, strumento, durata ed esito.
- **Scritture attribuite**: i documenti creati dall'assistente hanno
  `created_by` valorizzato e il registro attività dell'applicazione li mostra
  con l'utente, non anonimi.

Da tenere a mente:

- **I ruoli dell'interfaccia non valgono per l'MCP.** Chi ha il token può fare
  tutto quello che può fare l'amministratore, anche leggere dati che un
  collaboratore non vedrebbe. Il token è una chiave di amministrazione: va
  tenuto personale, non va condiviso e va cambiato se trapela.
- **Le cancellazioni restano all'interfaccia**: gli strumenti MCP non
  cancellano nulla, al massimo annullano un documento (operazione reversibile).
- **Cambiare il token**: modificare `MCP_TOKEN` nel `.env` e riavviare il
  servizio (`docker compose --profile mcp up -d`). Il token vecchio smette
  subito di funzionare.
- **Per non esporre nulla**: `MCP_ENABLED=false` (il default) e il servizio
  spento. Il profilo «mcp» di Docker Compose non viene avviato dal solo
  `docker compose up -d`.
- **Aggiornamenti**: usare sempre `docker compose --profile mcp up -d --build`,
  altrimenti l'immagine del server MCP resta quella vecchia. Un
  `docker compose down` lo rimuove: per riportarlo su,
  `docker compose --profile mcp up -d`.

## Prestazioni

- Le pagine più pesanti (dashboard, statistiche) tengono i conti in cache per
  un minuto; anche i prodotti sotto scorta e le tendine del registro attività
  sono in cache (60 s / 5 min).
- Ogni pagina riusa i gruppi dell'utente letti una sola volta e i conteggi dei
  badge (messaggi/posta) in cache per un minuto; i dati azienda restano in
  memoria del processo per 60 secondi.
- Email e PEC (preventivi, fatture, solleciti, SDI) si accodano dalla pagina e
  partono in background ogni 2 minuti (`invia_coda_email`): un server di posta
  lento non blocca più il sito. Gli invii falliti si vedono in Amministrazione
  → Coda email.
- I PDF dei documenti si riusano finché il documento non cambia (niente più
  render WeasyPrint ripetuti); il selettore dei componenti kit usa
  l'autocompletamento invece di 23k voci nel menu.
- La posta si sincronizza ogni 20 minuti (non ogni 5) e salta i messaggi già
  scaricati senza riscaricarli; il giro notturno resta alle 3:00.
- I log registrano i tempi di risposta (Gunicorn in microsecondi, Caddy in
  JSON) e le query oltre 1 secondo: per trovare le pagine lente basta
  `docker compose logs web db | grep …`.
- I menu di unità di misura e IVA sono condivisi fra tutte le righe: prima il
  modulo di un preventivo faceva una query per riga.
- Il modulo di un documento non scarica più tutto il catalogo articoli: i costi
  arrivano solo per le righe presenti e per l'articolo che si sceglie.
- Bootstrap, icone e grafici sono serviti dal gestionale (niente CDN esterni);
  i file statici hanno un nome con impronta e restano in cache a lungo.
- Limite di richieste: 120 ricerche al minuto per indirizzo.
- Gunicorn parte con `--preload`: viste e pagine principali si caricano una
  volta nel processo principale e i worker nascono già pronti. Prima, dopo ogni
  riciclo di un worker (circa due volte al giorno, contando i controlli di
  salute) la prima pagina impiegava 1-2 secondi.
- I ruoli dell'utente si leggono una volta per richiesta: l'indice della guida
  faceva una query per ogni pagina, la ricerca una per ogni sezione.

## Manutenzione consigliata

| Quando | Cosa |
| --- | --- |
| Ogni mese | Scaricare una copia di sicurezza dal gestionale |
| Ogni mese | Controllare che gli avvisi email arrivino (provocarne uno di prova) |
| Ogni 3 mesi | Prova di ripristino su una copia di prova |
| Ogni 6 mesi | Cambiare la password dell'amministratore e togliere gli accessi non più usati |
| Ogni 6 mesi | `apt upgrade` sul server e riavvio (`docker compose up -d --build`) |

## Cose da valutare (non ancora fatte)

L'accesso SSH è già solo con chiave (`PasswordAuthentication no`, `root` solo
con chiave) e fail2ban sorveglia `sshd`.

1. **Copia su un secondo posto**: oggi le copie stanno solo sul server (la copia
   via email non è attiva). Una copia automatica su spazio cloud
   (Backblaze/S3/Drive) con `rclone`, **cifrata** (es. `age` o `gpg`), è la
   protezione che manca contro un guasto del server.
2. **Copia via email cifrata**: se si attiva `BACKUP_EMAIL`, oggi il database
   viaggia in chiaro come allegato (clienti, dipendenti, fatture). Prima di
   attivarla conviene cifrare il file.
3. **Numerazione delle fatture**: il numero viene assegnato alla bozza. Se si
   elimina una bozza dopo che ne è stata creata un'altra, nella numerazione
   resta un buco. Assegnare il numero all'emissione evita il problema (è una
   modifica al flusso di fatturazione, da decidere).
4. **Registro presenze e ferie**: sono visibili a tutti i ruoli, comprese le
   assenze per malattia (dato sanitario). Valutare se limitarli a Personale e
   Amministratore.
5. **Dashboard**: fatturato, margini e fatture da incassare sono mostrati a
   tutti i ruoli (le statistiche complete invece solo a Vendite e
   Amministratore).
6. **Contenitore web senza root**: l'applicazione gira come `root` dentro il
   contenitore (il server MCP no). Passare a un utente dedicato richiede di
   sistemare i permessi del volume `media`.
7. **Ambiente di prova**: una seconda installazione (anche su questo PC) per
   provare le modifiche senza toccare i dati veri.
8. **Autenticazione a due fattori** per l'utente amministratore (richiede un
   pacchetto aggiuntivo, es. `django-otp`).
9. **Modulo di preventivi e ordini lunghi**: con 60-80 righe la pagina di
   modifica impiega 0,5-2 secondi sul server, quasi tutti per disegnare gli
   ~800 campi del modulo. Si può accelerare con widget disegnati senza
   template.
