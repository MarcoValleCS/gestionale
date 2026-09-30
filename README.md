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
- **Ordini cliente** – creati direttamente o dal preventivo accettato, con consegna
  prevista e stato consegne. Alla **conferma** il sistema confronta la giacenza con le
  righe e **genera automaticamente gli ordini fornitore** per le carenze, raggruppati
  per fornitore abituale dell'articolo (prezzo dal listino attivo, se presente).
- **Magazzino** – giacenze per magazzino, movimenti tracciati (carichi, scarichi,
  rettifiche), evidenza degli articoli **sotto scorta**, rettifica di inventario.
- **Ordini fornitore** – manuali o generati dagli ordini cliente, invio/conferma,
  **ricezione merce** (anche parziale) con carico automatico a magazzino, **stampa
  ordine fornitore** da inviare al fornitore.
- **Listini fornitori** – prezzo e sconto per articolo, validità temporale e
  **adeguamento percentuale di tutto il listino** (es. +3%) con storico delle variazioni.
- **Dashboard** – fatturato, margine e marginalità % del periodo (mese, anno, ultimi 12
  mesi), grafico fatturato/margine per mese, **marginalità per articolo e per fornitore**,
  valore del magazzino, articoli sotto scorta e ultimi documenti.
- **Utenti e ruoli** – Amministratore, Vendite, Acquisti, Magazzino, con pagine e azioni
  filtrate per ruolo. Utenti gestibili dall'interfaccia.
- **Creazione rapida** – dal preventivo, dall'ordine cliente e dall'ordine fornitore puoi
  creare con un clic («+» accanto al campo) un cliente, un fornitore o un articolo che
  non è ancora in anagrafica: viene creato e inserito subito nel documento.

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
  `DJANGO_CSRF_TRUSTED_ORIGINS`): Caddy ottiene il certificato HTTPS in automatico e serve
  anche i file caricati (logo).
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
templates/              interfaccia (Bootstrap 5, in italiano) e documenti stampabili
static/js/quick_create.js   creazione al volo di contatti e articoli
docker/                 entrypoint e configurazione Caddy
```

## Test

```bash
python manage.py test apps
```

Coprono il flusso completo (preventivo → ordine → ordine fornitore → ricezione →
consegna), il calcolo di totali e IVA mista, l'adeguamento dei listini, l'importazione
CSV/Excel, la creazione rapida, le statistiche di marginalità e i permessi dei ruoli.

## Prossime tappe suggerite

1. **Fatturazione elettronica SDI** (i campi P.IVA/SDI/PEC e i codici natura IVA sono già
   predisposti).
2. DDT / documento di trasporto e fatture di vendita.
3. Export Excel delle liste e reportistica avanzata (fatturato per cliente, stagionalità).
4. Invio email di preventivi e ordini direttamente dal gestionale.
5. Backup automatici pianificati sul VPS.
