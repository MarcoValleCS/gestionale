# Sicurezza, prestazioni e copie di sicurezza

Note pratiche per chi gestisce il server del gestionale. Non serve leggerle per
usare il programma: servono quando si mette mano al server.

## Copie di sicurezza

Ogni notte alle 3:00 il server salva:

- `db_AAAA-MM-GG_HHMM.sql.gz` — tutto il database (contatti, documenti, ore…)
- `media_AAAA-MM-GG_HHMM.tar.gz` — i file caricati (logo, foto, allegati)

Restano in `/opt/backups/gestionale` per 14 giorni, poi vengono cancellate le
più vecchie.

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

Lo script avvisa che i dati attuali vengono sostituiti e chiede conferma.
Prima di un ripristino è prudente fare una copia di quello che c'è ora.

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

## Prestazioni

- Le pagine più pesanti (dashboard, statistiche) tengono i conti in cache per
  un minuto.
- I menu di unità di misura e IVA sono condivisi fra tutte le righe: prima il
  modulo di un preventivo faceva una query per riga.
- Il modulo di un documento non scarica più tutto il catalogo articoli: i costi
  arrivano solo per le righe presenti e per l'articolo che si sceglie.
- Bootstrap, icone e grafici sono serviti dal gestionale (niente CDN esterni);
  i file statici hanno un nome con impronta e restano in cache a lungo.
- Limite di richieste: 120 ricerche al minuto per indirizzo.

## Manutenzione consigliata

| Quando | Cosa |
| --- | --- |
| Ogni mese | Scaricare una copia di sicurezza dal gestionale |
| Ogni mese | Controllare che gli avvisi email arrivino (provocarne uno di prova) |
| Ogni 3 mesi | Prova di ripristino su una copia di prova |
| Ogni 6 mesi | Cambiare la password dell'amministratore e togliere gli accessi non più usati |
| Ogni 6 mesi | `apt upgrade` sul server e riavvio (`docker compose up -d --build`) |

## Cose da valutare (non ancora fatte)

1. **Accesso SSH con chiave**: sul server esiste già una chiave funzionante, ma
   l'accesso con password e il login di `root` sono ancora permessi (protetti da
   fail2ban). Conviene disattivarli (`PasswordAuthentication no`,
   `PermitRootLogin prohibit-password`) dopo aver verificato di poter entrare
   con la chiave.
2. **Copia su un secondo posto**: oltre all'email, si può aggiungere una copia
   su spazio cloud (Backblaze/S3/Drive) con `rclone` o su un secondo server.
3. **Ambiente di prova**: una seconda installazione (anche su questo PC) per
   provare le modifiche senza toccare i dati veri.
4. **Autenticazione a due fattori** per l'utente amministratore (richiede un
   pacchetto aggiuntivo, es. `django-otp`).
