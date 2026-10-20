# Gestionale aziendale

Gestionale Aziendale: preventivi, ordini, magazzino, cantieri, personale e
fatturazione elettronica in un'unica applicazione Django, con l'interfaccia in
italiano.

Nasce per il lavoro di tutti i giorni di un'azienda che installa e manutiene
piscine e bagni: i documenti seguono la commessa dal preventivo alla consegna, e
quello che succede in cantiere finisce negli stessi numeri della dashboard.

Si usa in locale con SQLite, oppure su un VPS Linux con Docker e PostgreSQL.

## Funzioni

### Anagrafiche e catalogo

Clienti e fornitori con dati fiscali (P.IVA, CF, SDI, PEC), indirizzi,
condizioni di pagamento ed etichette colorate. Articoli con codice automatico,
aliquote IVA di vendita e di acquisto, scorta minima e codice a barre; varianti
generate da un articolo base; kit che nei documenti si aprono nei componenti,
così magazzino e ordini fornitore lavorano sui pezzi reali. I listini fornitori
hanno validità temporale, adeguamento percentuale dell'intero listino e storico
delle variazioni.

Contatti e articoli si possono creare al volo mentre si compila un documento, e
gli articoli si importano in massa da CSV o Excel.

### Vendite

Preventivi con righe, sconti, IVA per riga, sezioni con subtotale e riepilogo
IVA; modelli riutilizzabili da caricare con un clic; stampa A4 con logo e colore
aziendale; duplicazione. Dal preventivo accettato si crea l'ordine cliente.

Alla conferma dell'ordine il gestionale confronta la giacenza con le righe e
genera gli ordini fornitore per le quantità mancanti, raggruppati per fornitore
abituale e con il prezzo del listino attivo, se c'è.

Sul preventivo e sull'ordine si indica chi presenta il cliente e la percentuale
di provvigione. La provvigione viene scalata dal margine e ripartita sulle righe
in proporzione al loro valore; quando il preventivo diventa ordine la segue.

I documenti si possono inviare per email con il PDF allegato e un messaggio
personalizzato. L'invio passa da una coda e parte entro pochi minuti, così un
server di posta lento non blocca la pagina.

### Acquisti e magazzino

Giacenze per magazzino e movimenti tracciati (carichi, scarichi, rettifiche),
con evidenza degli articoli sotto scorta e rettifica di inventario. Ordini
fornitore manuali o generati dagli ordini cliente, con invio al fornitore,
ricezione anche parziale e carico automatico a magazzino. Fatture ricevute da
ordini d'acquisto o manuali, in stato da pagare o pagata.

### Cantieri e assistenza

Le commesse raccolgono preventivi, ordini, ordini fornitore, manutenzioni, foto
e allegati di un lavoro, con stato, responsabile, date e indirizzo. Le
manutenzioni ricorrenti (apertura e chiusura piscina, tagliandi) compaiono in
dashboard trenta giorni prima: da lì si segna l'intervento e si calcola la
scadenza successiva, oppure si crea il preventivo dal modello collegato.

### Amministrazione

DDT creati dagli ordini cliente (o manuali) che all'emissione scaricano il
magazzino e aggiornano l'ordine; stampa A4 senza prezzi con firma del
destinatario. Fatture emesse in bozza da ordini e DDT, con scadenza, scadenzario
e stati emessa, inviata, pagata.

Per lo SDI il gestionale genera l'XML FatturaPA (FPR12) controllando prima i
dati obbligatori, lo scarica oppure lo trasmette via PEC e registra l'esito
sulla fattura. La conservazione sostitutiva a norma resta fuori: va affidata a
un conservatore accreditato o al commercialista.

Registro attività su tutto ciò che viene creato, modificato o cancellato, e
copia di sicurezza scaricabile dall'interfaccia.

### Personale

Dipendenti con mansione, costo orario, ferie e permessi annui; ore registrate
per giornata e cantiere, con inserimento rapido dell'intera squadra; richieste
di ferie e permessi con approvazione e residuo calcolato; registro presenze
mensile.

I collaboratori esterni hanno un ruolo che apre solo la propria area: registrano
le ore e caricano le foto del cantiere, senza vedere prezzi, clienti o
documenti.

### Altro

Lead con bacheca per fasi della trattativa, valore stimato, prossima azione e
import dal modulo contatti del sito. Galleria fotografica con etichette e
collegamento al cantiere. Posta aziendale via IMAP, messaggi interni, guida
modificabile dall'interno.

Dashboard con fatturato, margine e marginalità del periodo, dettaglio per
articolo, fornitore, cliente e cantiere, valore del magazzino e prossime
scadenze. Le vendite si esportano in Excel, una riga per articolo venduto.

L'interfaccia è una PWA: si installa su Android e iPhone e ha una pagina di
fallback quando manca la connessione.

## Ruoli

| Ruolo          | Permessi principali                                                        |
| -------------- | -------------------------------------------------------------------------- |
| Amministratore | Tutto: impostazioni, utenti, dati anagrafici, documenti                    |
| Vendite        | Contatti, articoli, preventivi, ordini cliente                             |
| Acquisti       | Contatti, articoli, ordini fornitore, listini fornitori                    |
| Magazzino      | Giacenze, movimenti, rettifiche, ricezione merci, consegna ordini cliente  |
| Personale      | Dipendenti, registrazione ore, ferie e permessi                            |
| Collaboratore  | Solo la propria area: ore lavorate e foto dei cantieri                     |

## Più utenti insieme

Il gestionale è pensato per essere usato da più persone nello stesso momento.

- I numeri dei documenti vengono incrementati con un `UPDATE` atomico nel
  database, mai con lettura e riscrittura; il numero è anche `unique`, come
  ultima rete di sicurezza.
- Le giacenze si aggiornano con un `UPDATE` aritmetico: due scarichi
  contemporanei dello stesso articolo si sommano invece di sovrascriversi.
- Se due utenti salvano lo stesso documento, il secondo riceve un avviso e la
  sua modifica non viene applicata; la pagina si ricarica con i dati aggiornati.
- In locale SQLite lavora in WAL con attesa sui blocchi e transazioni
  `IMMEDIATE`. In produzione si usa PostgreSQL, che gestisce la concorrenza con
  blocchi di riga.

La sessione dura 12 ore dall'accesso e non si prolunga a ogni clic.

## Avvio in locale

Il repository contiene il codice, non il database. In locale si usa SQLite e
non serve il file `.env`.

```bash
# 1. Ambiente virtuale
py -m venv .venv              # Windows
python3 -m venv .venv         # Linux/macOS

# 2. Attivazione
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# 3. Dipendenze (versioni bloccate in requirements.txt)
pip install -r requirements.txt

# 4. Database e utente amministratore
python manage.py migrate
python manage.py createsuperuser

# 5. Dati di esempio (facoltativo)
python manage.py seed_demo                # clienti, articoli, preventivo, cantiere, personale
# python manage.py dati_dimostrativi      # dataset più ricco, con utenti per ogni ruolo

# 6. Avvio
python manage.py runserver
```

Apri <http://127.0.0.1:8000> e accedi con l'utente creato.

`seed_demo` non crea utenti; `dati_dimostrativi` crea un dataset completo con
utenti di prova per ogni ruolo e mostra le password a fine comando.

Ogni computer ha il proprio database di sviluppo (`db.sqlite3`, non versionato).
Per aggiornare un'altra copia del repository:

```bash
git pull
pip install -r requirements.txt
python manage.py migrate
```

## Test

```bash
python manage.py test apps
```

La suite copre il flusso completo (preventivo, ordine, ordine fornitore,
ricezione, consegna), DDT e fatture, email e XML FatturaPA, calcolo di totali e
IVA mista, listini, import CSV/Excel, cantieri, manutenzioni, personale,
provvigioni, export Excel, galleria, lead, PWA, permessi dei ruoli e strumenti
MCP.

Il workflow GitHub Actions in `.github/workflows/tests.yml` esegue tutti i test
a ogni push su `main` e a ogni pull request.

## Assistente MCP (locale)

`scripts/mcp_server.py` espone il gestionale a un client MCP via stdio, senza
aprire porte di rete: 89 strumenti, 46 di lettura in `scripts/mcp_read.py` e 43
di scrittura in `scripts/mcp_write.py`.

Le scritture riusano i servizi dell'applicazione (`apps/*/services.py`), così le
regole di business restano in un unico punto. Le cancellazioni restano
esclusive dell'interfaccia.

Gli elenchi sono paginati: la risposta contiene `totale`, `offset`, `limite`,
`has_more`, `prossimo_offset` e i `risultati`; per scorrere si ripete la
chiamata con `offset=prossimo_offset`.

```bash
pip install -r requirements-mcp.txt
.venv\Scripts\python.exe scripts\mcp_server.py
```

Nel client si configura come server stdio, con comando
`.venv\Scripts\python.exe` e argomento `scripts\mcp_server.py` (meglio con
percorsi assoluti). Gli strumenti sono verificati da `apps/core/tests_mcp.py`,
saltato se il pacchetto `mcp` non è installato.

### In produzione (HTTPS con token)

Lo stesso server può stare in produzione dietro Caddy, all'indirizzo
`https://<dominio>/mcp`. Ogni richiesta deve avere l'intestazione
`Authorization: Bearer <token>`: senza token non passa nulla.

```bash
# 1. Generare un token (segreto: non va condiviso)
openssl rand -hex 32

# 2. Nel .env
#    MCP_ENABLED=true
#    MCP_TOKEN=<il token generato>
#    MCP_USER=admin          # a chi sono attribuite le scritture

# 3. Avviare il servizio (profilo «mcp»: non parte con il solo «up -d»)
docker compose --profile mcp up -d
docker compose logs -f mcp
```

Nel client MCP si configura come server remoto:

```json
{
  "mcp": {
    "gestionale": {
      "type": "remote",
      "url": "https://gestionale.tuodominio.it/mcp",
      "headers": { "Authorization": "Bearer <il token>" }
    }
  }
}
```

Cosa protegge il server in produzione: token Bearer (confrontato a tempo
costante), allowlist degli IP (`MCP_ALLOWED_IPS`), limite di richieste al
minuto per token (`MCP_RATE_LIMIT`), protezione DNS rebinding (solo gli host
dichiarati sono ammessi) e log di ogni chiamata (chi, che strumento, quanto
tempo). Il contenitore non pubblica porte: l'unico ingresso è Caddy.

Verifica che sia vivo e che chieda il token:

```bash
# Senza token: deve rispondere 401
curl -s -o /dev/null -w "%{http_code}\n" https://gestionale.tuodominio.it/mcp

# Con il token: risponde con l'identificazione del server
curl -s -H "Authorization: Bearer <token>" \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"prova","version":"1"}}}' \
     https://gestionale.tuodominio.it/mcp
```

Le scritture sono attribuite all'utente indicato dal token: i documenti
risultano creati da una persona e il registro attività non mostra righe
anonime. Con più utenti si possono usare token diversi (`MCP_TOKENS`), anche
limitati alle sole letture (`mcp:sola-lettura`).

Il server MCP **non** applica i ruoli dell'interfaccia: chi ha il token può
fare tutto quello che può fare l'amministratore, compresi i dati che un
collaboratore non vedrebbe. Il token va quindi trattato come una chiave di
amministrazione.

## Deploy su VPS Linux (Docker)

Serve un VPS (Ubuntu 22.04 o 24.04, 1–2 GB di RAM bastano) e, per l'HTTPS
automatico, un dominio che punta all'IP del server.

```bash
# 1. Docker (una volta sola)
curl -fsSL https://get.docker.com | sh

# 2. Copia il progetto sul server (git clone oppure scp/zip)
cd /opt
git clone <tuo-repository> gestionale && cd gestionale

# 3. Configurazione
cp .env.example .env
nano .env       # dominio, chiave segreta, credenziali admin e DB

# Genera una chiave segreta valida:
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(50))"

# 4. Avvio (prima volta: alcuni minuti di build)
docker compose up -d --build

# 5. Controllo
docker compose ps
docker compose logs -f web
```

Con `DOMAIN`, `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` impostati
nel `.env`, Caddy ottiene il certificato HTTPS da solo. Con il solo IP si accede
via `http://<ip>`, senza certificato.

I file caricati sono serviti da Django solo agli utenti autenticati; Caddy non
li espone. Il primo amministratore viene creato dalle variabili
`DJANGO_SUPERUSER_*`: cambia la password al primo accesso.

All'avvio il contenitore `web` applica le migrazioni, raccoglie gli statici e
crea l'amministratore; `db` ha un healthcheck e `web` aspetta che sia pronto.

### Comandi utili sul server

```bash
docker compose ps                        # stato servizi (con salute)
docker compose logs -f web               # log applicazione
docker compose restart web               # riavvio applicazione
docker compose exec web python manage.py <comando>

# Aggiornamento del codice (con il server MCP: «--profile mcp» serve a
# ricostruire anche la sua immagine, altrimenti resterebbe indietro)
git pull && docker compose --profile mcp up -d --build
```

Se il server MCP è attivo, ricordati di usare `--profile mcp` anche per
`up`/`build`: senza, l'immagine del server MCP non viene ricostruita e
continua a girare il codice precedente.

## Sicurezza e backup

Le protezioni attive sono quelle standard di Django più qualche accorgimento:
accesso obbligatorio a tutte le pagine (sessioni di 12 ore), limite di 8
tentativi di accesso ogni 5 minuti per IP e 120 ricerche al minuto, header di
sicurezza e CSP, cookie `Secure` e `SameSite=Lax`, HTTPS con Caddy, upload
limitati e tipi eseguibili rifiutati, dipendenze bloccate a versioni precise.

Il server MCP (quando è attivo in produzione) è una seconda via d'accesso ai
dati: è protetto da un token Bearer, ma **non** dai ruoli dell'interfaccia.
Chi ha il token può fare tutto quello che può fare l'amministratore. Il token
va trattato come una chiave di amministrazione: personale, non condiviso.

Due script in `scripts/`:

```bash
# Backup database + file caricati (14 giorni di storico, verifica l'integrità)
./scripts/backup.sh                    # oppure ./scripts/backup.sh /percorso/backup

# Backup automatico ogni notte alle 3:00
crontab -e
0 3 * * * cd /opt/gestionale && ./scripts/backup.sh >> /var/log/gestionale-backup.log 2>&1

# Ripristino (chiede conferma e salva prima una copia dello stato attuale)
./scripts/restore.sh /opt/backups/gestionale/db_2026-10-01_0300.sql.gz
```

Il backup del database viene verificato subito con `gzip -t`; se è corrotto
arriva un avviso email. Il ripristino è atomico e non tocca i dati attuali
finché il file non è valido.

Le copie restano sullo stesso server: per averne una fuori, imposta
`BACKUP_EMAIL` nel `.env` oppure usa `rclone` verso uno spazio cloud, e provane
periodicamente il ripristino.

Hardening del VPS, firewall e note sulle prestazioni sono in
[`docs/sicurezza-e-backup.md`](docs/sicurezza-e-backup.md).

## Struttura del progetto

```
config/                 impostazioni Django (settings, urls)
apps/
  accounts/             utenti e ruoli
  core/                 IVA, unità di misura, etichette, pagamenti, numerazioni, dashboard,
                        posta IMAP, messaggi interni, guida, registro attività, backup
  contacts/             clienti e fornitori
  catalog/              articoli, categorie, import CSV/Excel
  inventory/            giacenze e movimenti di magazzino
  sales/                preventivi, ordini cliente, statistiche
  purchasing/           ordini fornitore e listini
  jobs/                 cantieri, manutenzioni programmate, foto
  hr/                   dipendenti, ore, ferie e permessi, presenze, collaboratori
  billing/              DDT, fatture emesse e ricevute, XML FatturaPA
  leads/                lead e pipeline commerciale
  gallery/              galleria fotografica con etichette
templates/              interfaccia (Bootstrap 5, in italiano) e documenti stampabili
static/js/              creazione rapida, autocomplete, modelli di preventivo, note formattabili
scripts/                server MCP, backup, ripristino, controllo del sito, icone PWA
docker/                 entrypoint e configurazione Caddy
docs/                   note operative
```

La logica di business sta in `apps/<app>/services.py`; le viste si limitano a
validare l'input e a scegliere il template.
