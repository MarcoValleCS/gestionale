# Consigli per gestire arredo bagno e piscine

Documento di lavoro: cosa si può fare nel gestionale per il tuo settore, cosa è
**già pronto** e cosa possiamo aggiungere. Le proposte sono ordinate per priorità
nella sezione finale: dimmi quali vuoi e le implemento.

> **Aggiornamento (ottobre 2026) – implementato:**
>
> - ✅ **Cantieri/commesse** (codice, stato, responsabile, indirizzo, documenti collegati)
> - ✅ **Sezioni nei preventivi/ordini** per ambiente o fase, con subtotali in schermo e stampa
> - ✅ **Manutenzioni programmate** con scadenze in dashboard, «Eseguita» e «Preventivo dal modello»
> - ✅ **Seriali e garanzie** (numero di serie, installazione, garanzia valida/scaduta)
> - ✅ **Allegati** su articoli e cantieri (protetti da login)
> - ✅ **Varianti articolo** generate da colore/finitura
> - ✅ **Kit/composizioni** con espansione automatica dei componenti nei documenti
> - ✅ **Sconto abituale cliente** proposto nelle righe
> - ✅ **Giorni di consegna fornitore** usati come data prevista negli ordini fornitore
> - ✅ **Riordino scorte** sotto il minimo alla conferma dell'ordine («e riordina scorte»)
> - ✅ **Statistiche estese**: finestra 1/3/6/12 mesi con navigazione nel tempo, dettaglio
>   per mese, fatturato per **cliente**, **articolo**, **fornitore** e **cantiere**
>
> Restano da fare: listini di vendita per articolo/cliente, DDT per cantiere,
> fatturazione elettronica, promemoria email delle manutenzioni.

---

## 1. Arredo bagno

### 1.1 Varianti colore, finitura e misura (proposta)

Oggi si gestiscono come articoli separati (es. `LAV-SOSP-70-BIANCO`,
`LAV-SOSP-70-NERO`). Funziona, ma diventa pesante con molti colori.

**Proposta**: modello di **varianti** sull'articolo (colore, finitura, misura) con
un solo articolo "padre" e varianti generate automaticamente. Nel preventivo si
sceglie l'articolo e poi la variante da un menu. Impatto medio, valore alto.

### 1.2 Modelli di preventivo per composizioni — ✅ **già pronto**

Hai i **Modelli di preventivo** (Vendite → Modelli preventivo): crea un modello
«Bagno completo – composizione base» con le righe tipo (mobile, lavabo, specchio,
rubinetteria, posa) e nel preventivo lo carichi con un clic. Puoi fare modelli
per fascia di prezzo (base/comfort/lusso) o per ambiente (bagno grande, bagno
servizio).

### 1.3 Ambienti e misure nel preventivo (proposta)

Per preventivi con più bagni (Bagno 1, Bagno 2…) servono **sezioni/ambienti**
nelle righe, con totale per ambiente, e **campi misure** per riga
(larghezza × altezza × profondità). Impatto medio, molto utile per il residenziale.

### 1.4 Servizi (posa, smaltimento, trasporto) — ✅ **già gestiti**

Gli articoli di tipo **servizio** (gestito a magazzino = No) non generano ordini
fornitore né scarichi: usali per posa, smaltimento, trasporto, sopralluogo.
Consiglio: crea un modello di preventivo che include già le righe servizio.

### 1.5 Kit e composizioni (proposta)

Un articolo «kit» che raggruppa componenti (es. mobile + lavabo + specchio) con
scorporo opzionale nel preventivo. Comodo anche per il magazzino: scarica i
componenti, non il kit.

### 1.6 Tempi di consegna fornitori (proposta)

Campo **giorni di consegna** sull'articolo: alla conferma dell'ordine cliente,
gli ordini fornitore generati propongono come data prevista oggi + giorni del
fornitore. Impatto basso, utile per comunicare le date ai clienti.

### 1.7 Etichette per showroom e stato merce — ✅ **già pronto**

Usa le etichette su articoli e clienti: «Espositore», «Pronta consegna»,
«Ultimo pezzo», «Cliente rivenditore», «Cantiere». Filtrabili nelle liste.

### 1.8 Schede tecniche, immagini e disegni (proposta)

Allegati (PDF/immagini) su articoli e su commesse. Impatto medio.

---

## 2. Piscine

### 2.1 Cantieri e commesse (proposta prioritaria)

Una piscina è un **progetto**, non un semplice ordine: serve un'entità
**Cantiere/Commessa** con cliente, indirizzo del cantiere, stato
(sopralluogo → preventivo → confermato → in esecuzione → collaudo → chiuso),
responsabile e documenti collegati (preventivi, ordini, ordini fornitore, DDT).
Tutte le statistiche restano per cliente, ma filtri anche per cantiere.
Impatto alto, valore altissimo per il vostro modo di lavorare.

### 2.2 Preventivi a fasi — ✅ **quasi pronto**

Con i **Modelli di preventivo** puoi già preparare «Piscina 8x4 – scavo»,
«– struttura», «– impianti», «– finiture», «– avvio», oppure un unico modello con
tutte le fasi come righe. Se vuoi i **totali per fase**, si fa con le
sezioni/ambienti del punto 1.3.

### 2.3 Materiali vs servizi — ✅ **già gestiti**

Scavo, posa, allaccio elettrico, avvio impianto = articoli servizio; pompe,
filtri, liner, robot = articoli a magazzino con fornitore abituale e listino.

### 2.4 Seriali, matricole e garanzie (proposta)

Registro dei **numeri di serie** per pompe, filtri, robot, con data di
installazione, garanzia e cantiere. In caso di guasto sai subito cosa è montato
e quando scade la garanzia. Impatto medio, valore alto sull'assistenza.

### 2.5 Manutenzione e contratti ricorrenti (proposta)

Piani di manutenzione (mensile, stagionale, apertura/chiusura): il gestionale
propone le **scadenze** con avvisi in dashboard e può generare il preventivo
ricorrente dal modello. Impatto medio-alto.

### 2.6 Sopralluoghi e km (proposta)

Righe servizio con **km/trasferta** (quantità × prezzo/km) e tappe di sopralluogo.
Bastano un articolo servizio «Trasferta» con prezzo per km e la descrizione in riga.

### 2.7 Foto, documenti e planimetrie (proposta)

Allegati per cantiere (foto, planimetria, permessi). Da abbinare al punto 2.1.

---

## 3. Utile a entrambi (trasversale)

- **Listini di vendita per cliente/fascia** (proposta): oggi hai i listini
  fornitori (acquisto); si può aggiungere il listino di vendita per cliente
  (privato, rivenditore, installatore) con sconti % automatici in riga.
- **Riordino automatico sotto scorta minima** (proposta): alla conferma
  dell'ordine, oltre alle carenze, genera ordini fornitore per portare gli
  articoli sotto scorta a un livello obiettivo.
- **DDT e documenti di trasporto per cantieri** (proposta): utile quando la
  merce parte verso il cantiere prima della fattura.
- **Fatturazione elettronica SDI** (già in programma): i campi fiscali e i codici
  natura IVA sono già predisposti.
- **Marginalità per cliente e per cantiere** (proposta): la dashboard oggi mostra
  articolo e fornitore; con i cantieri si aggiunge la marginalità per commessa.

---

## 4. Priorità consigliata

| Priorità | Cosa                                     | Perché                                        | Impatto |
| -------- | ---------------------------------------- | --------------------------------------------- | ------- |
| 1        | **Cantiere/Commessa**                    | Struttura tutto il lavoro piscine             | Alto    |
| 2        | **Kit/composizioni + sezioni preventivo**| Preventivi bagno più chiari e veloci          | Medio   |
| 3        | **Seriali e garanzie**                   | Assistenza post-vendita immediata             | Medio   |
| 4        | **Manutenzioni programmate**             | Ricavi ricorrenti e promemoria automatici     | Medio   |
| 5        | **Allegati** (articoli, cantieri)        | Foto e documenti dove servono                 | Medio   |
| 6        | **Varianti articolo**                    | Ordine nei colori/finiture                    | Alto    |
| 7        | **Listini vendita per cliente**          | Prezzi corretti senza errori                  | Medio   |
| 8        | **DDT per cantiere**                     | Tracciabilità consegne                        | Medio   |

## 5. Cosa usare da subito (già disponibile)

- **Modelli di preventivo** per bagni tipo e fasi piscina → *Vendite → Modelli preventivo*.
- **Etichette** per classificare clienti, articoli e showroom → *Impostazioni → Etichette*.
- **Articoli servizio** per posa, scavo, allaccio, manutenzione: non toccano il magazzino.
- **Scorta minima** per i ricambi più venduti: avviso in dashboard e ordine fornitore automatico alla conferma.
- **Listini fornitori con adeguamento %** per aggiornare i costi in un clic.
- **Marginalità per articolo e fornitore** in dashboard per capire dove guadagni.
