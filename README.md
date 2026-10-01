# Gestionale aziendale

Gestionale su misura in **Python + Django**, pensato per essere eseguito in locale
(Windows/macOS/Linux) e su un **VPS Linux** con Docker.

## Funzioni incluse

- **Contatti** – clienti e fornitori con dati fiscali (P.IVA, CF, SDI, PEC), indirizzi,
  condizioni di pagamento e **etichette colorate** per classificarli. Si possono creare
  al volo durante la compilazione di un documento.
- **Articoli** – codice automatico, categoria, unità di misura, **aliquote IVA per vendita
  e acquisto** (22%, 10%, 5%, 4%, esenti e codici natura per il futuro SDI), prezzo di
  vendita, prezzo di acquisto, fornitore abituale, **scorta minima**, etichette.
  Creabili al volo dai documenti e **importabili in massa da CSV/Excel** (vedi sotto).
- **Preventivi** – numerazione automatica, righe con quantità, U.d.M., prezzo, sconto %,
  IVA a scelta per ogni riga, totali e riepilogo IVA, **stampa/PDF grafica** con logo e
  colore aziendale, stati (bozza → inviato → accettato/rifiutato → convertito in ordine),
  duplicazione.
- **Modelli di preventivo** – modelli riutilizzabili con righe e condizioni preimpostate
  (es. «Bagno completo», «Piscina – manutenzione stagionale»): nel preventivo si scelgono
  e si caricano con un clic, senza riscrivere ogni volta le stesse righe.
- **Ordini cliente** – creati direttamente o dal preventivo accettato, con consegna
  prevista e stato consegne. Alla **conferma** il sistema confronta la giacenza con le
  righe e **genera automaticamente gli ordini fornitore** per le carenze, raggruppati
  per fornitore abituale dell'articolo (prezzo dal listino attivo, se presente).
- **Magazzino** – giacenze per magazzino, movimenti tracciati (carichi, scarichi,
  rettifiche), evidenza degli articoli **sotto scorta**, rettifica di inventario.
- **Ordini fornitore** – manuali o generati dagli ordini cliente, invio/conferma,
  **ricezione merce** (anche parziale) con carico automatico a magazzino, **stampa
  ordine fornitore** da inviare al fornitore. Alla conferma dell'ordine cliente puoi
  anche **riordinare le scorte** sotto il minimo con un clic.
- **Cantieri/commesse** – raggruppano preventivi, ordini, ordini fornitore, manutenzioni,
  seriali e allegati di un lavoro (es. una piscina), con stato, responsabile, date e indirizzo.
- **Manutenzioni programmate** – canoni e interventi ricorrenti (apertura/chiusura piscina,
  tagliandi): promemoria in dashboard a 30 giorni, «Eseguita» calcola la prossima scadenza,
  «Preventivo» crea il preventivo dal modello collegato.
- **Seriali e garanzie** – registro dei numeri di serie installati (pompe, filtri, robot) con
  cliente, cantiere, data di installazione e garanzia (stato in garanzia/scaduta).
- **Personale e presenze** – anagrafica dipendenti (mansione, costo orario, ferie e permessi
  annui); **registrazione ore** per giornata con tipo (ordinario, straordinario, trasferta) e
  collegamento al cantiere, con inserimento rapido delle ore di tutta la squadra in una sola
  schermata; **ferie e permessi** con richiesta, approvazione/rifiuto e calcolo automatico del
  residuo (ferie in giorni, permessi in ore); **registro presenze** mensile con ore e assenze
  giorno per giorno e sigle (F ferie, P permessi, M malattia).
- **Allegati** – carica foto, schede tecniche e documenti su articoli e cantieri; i file sono
  serviti solo agli utenti autenticati.
- **Varianti articolo** – genera le versioni colore/finitura di un articolo in un clic
  (ogni variante ha codice, giacenza e prezzi propri).
- **Kit/composizioni** – articoli che raggruppano componenti (es. mobile + lavabo + specchio):
  nel preventivo si espandono da soli con i componenti a prezzo zero, così magazzino e ordini
  fornitore lavorano sui componenti reali.
- **Sezioni nei documenti** – righe raggruppabili per ambiente o fase («Bagno 1», «Bagno
  padronale», «Scavo») con subtotale per sezione in schermo e in stampa.
- **Condizioni formattabili** – le note che finiscono in stampa si scrivono con un
  editor semplice: grassetto, corsivo, sottolineato, dimensione del carattere, elenchi e
  allineamento. Il contenuto viene ripulito da una lista bianca prima di essere salvato e
  reso, quindi non può veicolare script o immagini.
- **Collaboratori esterni** – per il lavoro che si dà a terzi (scavo, reinterro,
  elettricista): anagrafica con ditta, specializzazione e compenso orario; le ore si
  registrano per giornata indicando **quante ore, quale giorno e su quale cantiere**.
  Creando per loro un utente con il solo ruolo «Collaboratore», entrano e rendicontano
  da soli: quell'utente vede **unicamente la propria area** e non può accedere a
  prezzi, clienti, documenti o statistiche. In più l'ufficio vede tutte le ore
  raccolte, filtrabili per collaboratore, cantiere e periodo.
- **Sconto abituale cliente** – percentuale proposta automaticamente nelle righe di
  preventivi e ordini.
- **DDT** – documenti di trasporto creati dagli ordini cliente (o manuali), con causale,
  vettore, colli, peso e destinazione; all'emissione scaricano il magazzino e aggiornano
  l'ordine. Stampa A4 senza prezzi con firma del destinatario.
- **Fatture emesse e ricevute** – fatture in bozza create da ordini/DDT o manuali, con
  scadenza, stato (emessa, inviata, pagata) e stampa grafica; fatture fornitore da ordini
  d'acquisto o manuali, con stato da pagare/pagata. In dashboard gli alert «da incassare»
  e «da pagare».
- **Invio fatture via email** – dalla scheda della fattura invii al cliente l'email con
  **PDF in allegato** (generato dal gestionale) e il messaggio che preferisci; lo stato
  passa automaticamente a «Inviata».
- **Fatturazione elettronica (SDI)** – genera il file **XML FatturaPA** (formato FPR12)
  con i controlli sui dati obbligatori, lo scarica o lo **trasmette allo SDI via PEC**;
  registri l'esito (consegnata, accettata, scartata…) sulla scheda della fattura.
- **Webapp installabile** – il gestionale è una **PWA**: su Android si installa da Chrome
  («Installa app»), su iPhone da Safari («Aggiungi a Home»), con icona, avvio a pieno
  schermo e pagina offline quando manca la connessione.
- **Listini fornitori** – prezzo e sconto per articolo, validità temporale e
  **adeguamento percentuale di tutto il listino** (es. +3%) con storico delle variazioni.
- **Invio preventivi via email** – dalla scheda del preventivo invii al cliente l'email con
  il **PDF in allegato** (generato dal gestionale) e il messaggio che preferisci; l'invio
  porta automaticamente il preventivo da «Bozza» a «Inviato».
- **Chi ha creato il documento** – l'elenco dei preventivi mostra chi l'ha inserito, con un
  filtro per utente e il pulsante «Solo i miei» per vedere in un clic i propri preventivi.
- **Provvigione a chi presenta il cliente** – su preventivo e ordine indichi **a chi** va la
  provvigione (un contatto in anagrafica) e la **percentuale sull'imponibile**. La provvigione
  **erode il margine** in dashboard e in tutte le statistiche, ripartita sulle righe in
  proporzione al loro valore; segue automaticamente il preventivo quando lo converti in ordine.
- **Esportazione Excel** – dalla dashboard scarichi il **dettaglio delle vendite** del periodo
  scelto, una riga per articolo venduto: data, documento, cliente, venditore, articolo,
  quantità, prezzo, sconto, imponibile, costo, provvigione, margine e margine %, con riga dei
  totali. Pronto per filtri e tabelle pivot.
- **Dashboard** – fatturato, margine e marginalità % del periodo (mese, anno, ultimi 12
  mesi), **grafico navigabile** (1/3/6/12 mesi, torna al periodo precedente) con dettaglio
  mese per mese, **marginalità per articolo, fornitore, cliente e cantiere**, valore del
  magazzino, articoli sotto scorta, manutenzioni in scadenza e ultimi documenti.
- **Utenti e ruoli** – Amministratore, Vendite, Acquisti, Magazzino, con pagine e azioni
  filtrate per ruolo. Utenti gestibili dall'interfaccia.
- **Creazione rapida e ricerca a digitazione** – nei documenti clienti, fornitori e articoli
  si cercano **scrivendo** (per nome, codice, P.IVA, codice fiscale, città; per gli articoli
  anche per codice a barre): bastano poche lettere e compare l'elenco dei risultati con i
  dati principali. Se l'elemento non esiste, dalla stessa tendina scegli **«Crea «...»»**
  (o il pulsante «+»): viene creato al volo, con anche il **codice fiscale**, e inserito
  subito nel documento.

Non sono ancora inclusi: fatturazione elettronica (SDI), DDT, fatture di vendita/acquisto.
Sono i candidati naturali per le prossime fasi.

## Fatturato e marginalità

- **Fatturato** = imponibile (IVA esclusa) degli **ordini cliente consegnati** nel periodo.
- **Margine** = fatturato − costo del venduto. Il costo unitario viene fissato alla
  conferma dell'ordine usando il listino del fornitore abituale (o il prezzo di acquisto
  dell'articolo); per gli ordini non ancora confermati si usa il prezzo di acquisto attuale.
- I dati si popolano man mano che registri le consegne («Consegna e scarica magazzino»).

## Importazione articoli da CSV o Excel

Da **Articoli → Importa CSV/Excel**. Il file deve avere le intestazioni nella prima riga
(ordine libero, sono riconosciute anche varianti come `nome`, `um`, `prezzo`, `costo`,
`ean`, `supplier`). Unica colonna obbligatoria: `descrizione`. C'è un **modello CSV
scaricabile** direttamente dalla pagina di importazione.

| Colonna          | Obbligatoria | Descrizione                                                        | Esempio                     |
| ---------------- | ------------ | ------------------------------------------------------------------ | --------------------------- |
| `descrizione`    | sì           | Nome dell'articolo                                                  | Bullone M8 zincato          |
| `codice`         | no           | Codice articolo: se esistente l'articolo viene **aggiornato**       | ART00012                    |
| `categoria`      | no           | Categoria (creata se non esiste)                                    | Ricambi                     |
| `unita_misura`   | no           | Codice o nome dell'unità di misura                                  | PZ                          |
| `prezzo_vendita` | no           | Prezzo di vendita senza IVA (virgola o punto)                       | 0,35                        |
| `iva_vendita`    | no           | Codice aliquota o valore (default: aliquota vendite predefinita)    | 22                          |
| `prezzo_acquisto`| no           | Prezzo di acquisto dal fornitore senza IVA                          | 0,18                        |
| `iva_acquisto`   | no           | Aliquota di acquisto (default: aliquota acquisti predefinita)       | 22                          |
| `barcode`        | no           | Codice a barre / EAN                                                | 8012345678901               |
| `scorta_minima`  | no           | Scorta minima per l'avviso sotto scorta                             | 500                         |
| `fornitore`      | no           | Fornitore abituale (creato se non esiste)                           | Ferramenta Bianchi S.p.A.   |
| `etichette`      | no           | Etichette separate da virgola (create se non esistono)              | Promozione, Nuovo           |
| `note`           | no           | Note interne                                                        |                             |
| `attivo`         | no           | sì / no (default sì)                                                | sì                          |

Regole di importazione:

1. Se il **codice** esiste già, l'articolo viene aggiornato; altrimenti lo si cerca per
   nome; se non c'è, viene creato.
2. Unità di misura, categorie, fornitori ed etichette mancanti vengono creati in automatico.
3. Con l'opzione **«Aggiorna il listino del fornitore»** il `prezzo_acquisto` importato
   crea/aggiorna anche la voce di listino del fornitore (usata poi dagli ordini fornitore).
4. Le righe con errori vengono segnalate con il numero di riga, senza bloccare le altre.
5. Formati accettati: `.csv` (separatore `;` o `,`, codifica UTF-8 o Windows) e `.xlsx`.

## Documenti stampabili

Preventivi, conferme d'ordine e ordini fornitore hanno un **modello grafico in A4** con:

- intestazione con **logo aziendale** (caricabile in *Impostazioni → Dati azienda*);
- **colore principale** personalizzabile (stesso pannello);
- riquadro destinatario, dati documento (data, validità, pagamento, riferimenti);
- tabella righe con IVA e sconti, totali con riepilogo IVA per aliquota;
- spazio per **accettazione/timbro e firma** su preventivi e conferme d'ordine;
- piè di pagina con P.IVA e IBAN.

Dal pulsante «Stampa / Salva PDF» si ottiene un PDF pronto da inviare al cliente o al
fornitore.

## Fatturazione elettronica (SDI)

Dalla scheda di una fattura emessa, il riquadro **«Fattura elettronica (SDI)»** permette di:

1. **Generare l'XML FatturaPA** (versione FPR12, tipo documento TD01): il sistema controlla
   prima i dati obbligatori (P.IVA e indirizzo azienda, P.IVA/CF del cliente, codice
   destinatario o PEC, codice natura per le aliquote a 0%) e segnala cosa manca.
2. **Scaricare l'XML** per caricarlo su un intermediario o sul portale del commercialista.
3. **Trasmettere allo SDI via PEC**: usa le credenziali `EMAIL_*` del file `.env` (impostale
   sulla casella PEC aziendale) e invia il file a `SDI_PEC_ADDRESS`
   (predefinito `sdi01@pec.fatturapa.it`).
4. **Aggiornare l'esito** (inviata, consegnata, accettata, scartata, mancata consegna) con
   una nota, così hai lo storico sulla fattura.

Impostazioni consigliate in `.env`: `EMAIL_HOST` = SMTP del provider PEC,
`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` = casella PEC, `DEFAULT_FROM_EMAIL` = indirizzo PEC.

> Nota: la **conservazione sostitutiva a norma** (che tiene l'XML a valore legale per 10 anni)
> va fatta con un conservatore accreditato (AgID) o tramite il vostro commercialista; il
> gestionale genera e trasmette il file, non sostituisce il conservatore.

## Webapp su telefono (PWA)

Il gestionale è una **webapp installabile**, con interfaccia ottimizzata per il telefono
(menu a scomparsa, tabelle scorrevoli, spaziature compatte, area sicura per i notch).

- **Android (Chrome)**: apri il gestionale, menu ⋮ → **«Aggiungi a schermata Home»** /
  «Installa app» (oppure usa la voce «Installa app sul telefono» nel menu utente).
- **iPhone (Safari)**: Condividi → **«Aggiungi a Home»**.
- All'apertura dalla home parte a pieno schermo, con icona dedicata; se manca la
  connessione compare una pagina «Sei offline» con il tasto Riprova.

L'installazione richiede **HTTPS** (con Caddy e dominio è automatico; `localhost` va bene
per le prove).

## Lavorare da un altro computer

Il repository contiene il **codice**, non il database. Su un nuovo PC:

```bash
git clone https://github.com/<tuo-utente>/gestionale.git
cd gestionale

# ambiente virtuale
py -m venv .venv                  # Windows
python3 -m venv .venv             # Linux/macOS
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux/macOS

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # dati di esempio (facoltativo)
python manage.py runserver
```

In locale **non serve il file `.env`**: di default il gestionale usa SQLite e le impostazioni
di sviluppo. Il file `.env` è pensato per il VPS (PostgreSQL, HTTPS, credenziali).

Ogni computer ha il proprio database di sviluppo (`db.sqlite3`, non versionato); i dati veri
sono sul VPS, che si aggiorna con `git pull && docker compose up -d --build`.

## Test automatici su GitHub

Il repository include un workflow GitHub Actions (`.github/workflows/tests.yml`) che esegue
tutti i test a ogni push o pull request: nella pagina del repository, scheda **Actions**,
vedi se il codice è a posto prima di metterlo online.

## Avvio in locale (Windows / Linux / macOS)

```bash
# 1. Ambiente virtuale
py -m venv .venv              # Windows
python3 -m venv .venv         # Linux/macOS

# 2. Attivazione
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# 3. Dipendenze
pip install -r requirements.txt

# 4. Database e dati iniziali (in locale usa SQLite, zero configurazione)
python manage.py migrate
python manage.py createsuperuser     # oppure: python manage.py seed_demo per un utente admin
python manage.py seed_demo           # dati di esempio (opzionale ma consigliato)

# 5. Avvio
python manage.py runserver
```

Apri <http://127.0.0.1:8000> e accedi con l'utente creato.

## Ruoli

| Ruolo          | Permessi principali                                                       |
| -------------- | ------------------------------------------------------------------------- |
| Amministratore | Tutto: impostazioni, utenti, dati anagrafici, documenti                   |
| Vendite        | Contatti, articoli, preventivi, ordini cliente                            |
| Acquisti       | Contatti, articoli, ordini fornitore, listini fornitori                   |
| Magazzino      | Giacenze, movimenti, rettifiche, ricezione merci, consegna ordini cliente |
| Personale      | Dipendenti, registrazione ore, ferie e permessi                           |
| Collaboratore  | **Solo** la propria area: registra le ore lavorate sui cantieri            |

## Più utenti in contemporanea

Il gestionale è pensato per essere usato da più persone insieme (es. 8 utenti).
Sui dati condivisi sono attive queste protezioni:

- **Numeri documento mai duplicati.** Il contatore dei documenti (preventivi, ordini,
  DDT, fatture) viene incrementato con un `UPDATE` atomico a livello di database, non
  con una lettura seguita da una scrittura. Due utenti che creano un documento nello
  stesso istante ottengono numeri diversi. Il numero è anche `unique` nel database,
  come ultima rete di sicurezza.
- **Giacenze sempre corrette.** Anche il magazzino viene aggiornato con un `UPDATE`
  aritmetico: due scarichi contemporanei dello stesso articolo si sommano invece di
  sovrascriversi, e il controllo sulla disponibilità resta valido.
- **Modifiche contemporanee segnalate.** Se due utenti aprono lo stesso documento e lo
  salvano entrambi, il secondo riceve un avviso e la sua modifica **non** viene salvata:
  la pagina si ricarica con i dati aggiornati, evitando di perdere il lavoro dell'altro.
- **SQLite configurato per la concorrenza** (uso locale): `WAL` attivo, attesa di 20
  secondi sui blocchi e transazioni `IMMEDIATE`. In produzione su VPS si usa PostgreSQL,
  che gestisce la concorrenza con blocchi di riga.
- **Sessione salvata solo quando cambia**, non a ogni pagina aperta: con più utenti
  collegati significa molte scritture in meno.

> Nota: la sessione dura 12 ore dall'accesso e non si prolunga a ogni clic. Dopo 12 ore
> occorre rientrare.


## Flusso di lavoro tipico

1. Crei il **preventivo** per il cliente (righe con articolo, U.d.M., prezzo, IVA).
   Cliente o articolo mancanti? Creali al volo con il pulsante «+».
2. Stampic o invii; quando il cliente accetta, premi **«Accettato dal cliente»** e poi
   **«Crea ordine cliente»**.
3. Alla **conferma** dell'ordine, se non hai giacenza sufficiente, il gestionale crea da
   solo gli **ordini fornitore** (uno per fornitore) con le quantità mancanti.
4. Quando arriva la merce, in ogni ordine fornitore premi **«Ricevi merce»**: la giacenza
   si aggiorna.
5. Sull'ordine cliente premi **«Consegna e scarica magazzino»**: la giacenza si aggiorna,
   l'ordine si chiude e i dati di fatturato/margine finiscono in dashboard.

## Deploy su VPS Linux (Docker)

Serve un VPS (es. Ubuntu 22.04/24.04, 1–2 GB di RAM bastano) e, se vuoi l'HTTPS
automatico, un dominio che punta all'IP del VPS.

```bash
# 1. Docker (una volta sola)
curl -fsSL https://get.docker.com | sh

# 2. Copia il progetto sul server (git clone oppure scp/zip)
cd /opt
git clone <tuo-repository> gestionale && cd gestionale

# 3. Configurazione
cp .env.example .env
nano .env       # compila dominio, chiave segreta, credenziali admin e DB

# Genera una chiave segreta valida:
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(50))"

# 4. Avvio (prima volta: alcuni minuti di build)
docker compose up -d --build

# 5. Controllo
docker compose logs -f web
```

- Con un **dominio** configurato in `.env` (`DOMAIN`, `DJANGO_ALLOWED_HOSTS`,
  `DJANGO_CSRF_TRUSTED_ORIGINS`): Caddy ottiene il certificato HTTPS in automatico.
- I **file caricati** (logo, allegati) sono serviti da Django **solo agli utenti
  autenticati**; Caddy non li espone direttamente.
- Con il **solo IP**: imposta `DOMAIN=<ip-del-vps>` e `DJANGO_ALLOWED_HOSTS=<ip>`; si
  accede via `http://<ip>` (senza certificato).
- Il primo utente amministratore viene creato automaticamente dalle variabili
  `DJANGO_SUPERUSER_*` del file `.env`. **Cambia la password al primo accesso.**

### Comandi utili sul server

```bash
docker compose ps                        # stato servizi
docker compose logs -f web               # log applicazione
docker compose restart web               # riavvio applicazione

# Backup del database
docker compose exec db pg_dump -U gestionale gestionale > backup-$(date +%F).sql

# Ripristino di un backup
cat backup-2026-01-01.sql | docker compose exec -T db psql -U gestionale gestionale

# Aggiornamento del codice
git pull && docker compose up -d --build
```

## Sicurezza, backup e prestazioni

### Protezioni già attive

- **Accesso obbligatorio** a tutte le pagine (anche agli endpoint di ricerca), sessioni di 12 ore.
- **Anti-abuso** (`apps/core/middleware.py`): massimo 8 tentativi di accesso ogni 5 minuti per
  IP e 120 ricerche al minuto; oltre la soglia risponde 429. I contatori sono condivisi tra i
  processi grazie alla cache su file.
- **Header di sicurezza** (Django + Caddy): `X-Frame-Options: DENY`, `X-Content-Type-Options`,
  `Referrer-Policy`, `Permissions-Policy`, HSTS quando HTTPS è attivo, header `Server` rimosso.
- **HTTPS automatico** con Caddy (certificato Let's Encrypt) quando c'è un dominio.
- **Limiti di caricamento**: 25 MB per richiesta in Caddy, 10 MB in Django (import Excel).
- **Cookie** di sessione e CSRF `Secure` con HTTPS, `SameSite=Lax`, `HttpOnly`.

### Protezioni consigliate sul VPS (una volta sola)

```bash
sudo apt update && sudo apt install -y ufw fail2ban unattended-upgrades

# Firewall: solo SSH, HTTP e HTTPS
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable
sudo systemctl enable --now fail2ban

# Aggiornamenti di sicurezza automatici
sudo dpkg-reconfigure -plow unattended-upgrades

# Swap: indispensabile con 1 GB di RAM (evita il blocco su picchi di lavoro)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```

**DDoS**: con 1 vCPU la difesa migliore è non esporre l'IP. Metti il dominio dietro
**Cloudflare (piano gratuito)**: assorbe gli attacchi volumetrici, nasconde l'IP del VPS e
aggiunge WAF di base. Opzionale: `sudo apt install crowdsec` per bloccare scanner e bot a
livello di sistema. Docker è già configurato con rotazione dei log (10 MB × 3 file per
servizio), così il disco da 10 GB non si riempie.

### Backup

Due script pronti in `scripts/`:

```bash
# Backup database + file caricati (mantiene 14 giorni)
./scripts/backup.sh                    # oppure ./scripts/backup.sh /percorso/backup

# Backup automatico ogni notte alle 3:00
crontab -e
0 3 * * * cd /opt/gestionale && ./scripts/backup.sh >> /var/log/gestionale-backup.log 2>&1

# Ripristino (chiede conferma prima di sovrascrivere)
./scripts/restore.sh /opt/backups/gestionale/db_2026-10-01_0300.sql.gz
```

Copia periodicamente i backup anche fuori dal VPS (rsync verso un altro server, cloud):
il backup sullo stesso disco non protegge da guasti.

### Prestazioni

- **PostgreSQL tarato** per 1 GB di RAM: `shared_buffers=128MB`,
  `effective_cache_size=384MB`, `work_mem=4MB`, `max_connections=25`.
- **Indici** sulle query più usate: stato+data su preventivi e ordini, nome+attivo su contatti
  e articoli, codice a barre, data sui movimenti di magazzino, P.IVA sui contatti.
- **Gunicorn**: 2 worker con thread, riciclo periodico dei worker, timeout 60s — tarato per 1 vCPU.
- **Cache su file** condivisa e **Whitenoise** per i file statici (nessun nginx separato).

## Struttura del progetto

```
config/                 impostazioni Django (settings, urls)
apps/
  accounts/             utenti e ruoli
  core/                 IVA, unità di misura, etichette, pagamenti, numerazioni, dashboard
  contacts/             clienti e fornitori
  catalog/              articoli, categorie, import CSV/Excel
  inventory/            giacenze e movimenti di magazzino
  sales/                preventivi, ordini cliente, statistiche (fatturato/marginalità)
  purchasing/           ordini fornitore e listini
  jobs/                 cantieri, manutenzioni programmate, seriali/garanzie
  hr/                   dipendenti, registrazione ore, ferie/permessi, registro presenze
  billing/              DDT, fatture emesse/ricevute
templates/              interfaccia (Bootstrap 5, in italiano) e documenti stampabili
static/js/quick_create.js   creazione al volo di contatti e articoli
static/js/autocomplete.js   ricerca a digitazione
static/js/quote_template.js caricamento dei modelli di preventivo
scripts/                backup e ripristino per il VPS
docker/                 entrypoint e configurazione Caddy
CONSIGLI-ARREDO-BAGNO-PISCINE.md   idee e roadmap per il tuo settore
```

## Test

```bash
python manage.py test apps
```

Coprono il flusso completo (preventivo → ordine → ordine fornitore → ricezione →
consegna), DDT e fatture emesse/ricevute, email e XML FatturaPA (SDI), il calcolo di
totali e IVA mista, l'adeguamento dei listini, l'importazione
CSV/Excel, la creazione rapida, i modelli di preventivo, cantieri, manutenzioni, seriali,
allegati, varianti, kit, sezioni, statistiche di marginalità, il personale (dipendenti,
ore, ferie e registro presenze), l'invio dei preventivi per email, le provvigioni,
l'esportazione Excel, i collaboratori esterni con la loro area riservata, le PWA (manifest e service
worker), le protezioni anti-abuso e i permessi dei ruoli.

## Prossime tappe suggerite

1. **Fatturazione elettronica SDI** (i campi P.IVA/SDI/PEC e i codici natura IVA sono già
   predisposti).
2. DDT / documento di trasporto e fatture di vendita.
3. Export Excel delle liste e reportistica avanzata (fatturato per cliente, stagionalità).
4. Invio email di preventivi e ordini direttamente dal gestionale.
5. Backup automatici pianificati sul VPS.
