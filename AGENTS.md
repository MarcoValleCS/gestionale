# AGENTS.md — Gestionale (Django)

Gestionale aziendale in Django, monolite, UI e codice **in italiano**.
Target: uso locale (SQLite) e VPS Linux con Docker (PostgreSQL + Caddy).

## Comandi

Il venv è `.venv`. Usare sempre l'interprete esplicito (l'ambiente non è
attivato di default).

```bash
# Test (tutti)
.venv\Scripts\python.exe manage.py test apps

# Un file di test / una classe / un metodo
.venv\Scripts\python.exe manage.py test apps.core.tests_concurrency
.venv\Scripts\python.exe manage.py test apps.sales.tests.SomeClass
.venv\Scripts\python.exe manage.py test apps.sales.tests.SomeClass.test_x

# Server e database
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py makemigrations <app>
.venv\Scripts\python.exe manage.py runserver
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py seed_demo        # dati minimi
.venv\Scripts\python.exe manage.py dati_dimostrativi  # dataset completo + utenti per ogni ruolo

# Server MCP locale (trasporto stdio)
.venv\Scripts\python.exe scripts\mcp_server.py
```

- **Non esiste linter, formatter né typechecker** (no `pyproject.toml`, ruff,
  flake8, black, mypy). L'unica verifica è la suite di test. Non inventare
  comandi di lint.
- **La suite completa è lenta** (~11 minuti, 483 test). Per un cambiamento
  localizzato puntare al file interessato invece di lanciare `test apps`.
- **I test si eseguono solo con `manage.py test`.** `config/settings.py` fa
  `IN_TEST = "test" in sys.argv`: sotto pytest la cache resterebbe attiva e i
  test che scrivono e rileggono dati fallirebbero.
- CI: `.github/workflows/tests.yml`, Python 3.13 su ubuntu-latest,
  `python manage.py test apps --verbosity=2`, su push a `main` e su ogni PR.
- Le migrazioni sono versionate per app: un cambio a un modello richiede
  `makemigrations` + il file di migrazione nel commit.

## Gotcha: `.env` non viene caricato da Django

Non c'è `python-dotenv`. `config/settings.py` legge solo `os.environ`.
In Docker il file arriva da `env_file: .env` in `docker-compose.yml`; **in locale
`.env` viene ignorato** e valgono i default (SQLite, DEBUG=True, nessuna email).
Per provare una configurazione a mano, impostare le variabili nella shell.

## Dove sta la logica

- **Business logic in `apps/<app>/services.py`**, non nelle viste:
  `sales`, `purchasing`, `billing`, `inventory`. Gli strumenti MCP di scrittura
  riusano questi servizi, quindi duplicare la regola in una vista la rompe due
  volte.
- Numerazione documenti: `apps/core/models.py::NumberSequence.take_next_number()`.
  Giacenze: `apps/inventory/services.py::register_movement()`.
  Non chiamare `select_for_update`: su SQLite non fa nulla (il dev DB è SQLite).
- Totali documento: il mixin `TotalsDocument.recalculate()` in
  `apps/sales/models.py`; le righe si espandono con `espandi_kit()`.
- Arrotondamenti **solo** da `apps/core/rounding.py` (`round2/round3/round4`,
  `ROUND_HALF_UP`). Python arrotonda a metà pari (`0.665 → 0.66`): in
  fatturazione è un bug, ed è già successo in questo repo.
- Modelli "significativi" vanno dichiarati in `apps/core/apps.py::ready()` con
  `activity.sorveglia(...)`, altrimenti non finiscono nel registro attività.
- I PDF passano da `apps/core/pdf.py::render_pdf()`. Se WeasyPrint non è
  utilizzabile ritorna `None` e l'app continua (qui è installato e funziona).

## Concorrenza (il repo è pensato per più utenti insieme)

- Numeri documento e giacenze si aggiornano con `UPDATE` aritmetico in SQL
  (`F("next_number") + 1`), **mai** lettura + scrittura in Python.
  `apps/core/tests_concurrency.py` verifica l'SQL con `CaptureQueriesContext`:
  un refactor "più pulito" in Python rompe il test.
- Il DB di test è un file (`test_db.sqlite3`), non in memoria, di proposito:
  WAL e `busy_timeout` non agiscono in memoria e i test di concorrenza
  (thread + barriera) non riprodurrebbero la situazione reale.
- `ConflictAwareUpdateView` (`apps/core/concurrency.py`) va **primo** nella
  lista di classi e aggancia `dispatch`, non `post` (molte viste di documento
  ridefiniscono `post` per le righe).
  ```python
  class QuoteUpdateView(ConflictAwareUpdateView, RoleRequiredMixin, UpdateView):
  ```

## Viste, permessi, template

- `django.contrib.auth.middleware.LoginRequiredMiddleware` è globale: ogni
  pagina richiede il login. Le eccezioni sono marcate con
  `@login_not_required` (PWA, `/termini/`) in fondo ad `apps/core/views.py`.
- I ruoli sono **Group Django con nomi italiani** (`apps/accounts/permissions.py`):
  `role_required(...)` per viste a funzione, `RoleRequiredMixin` + `allowed_roles`
  per CBV. `is_superuser` bypassa tutto.
- Un utente con **solo** il ruolo `Collaboratore` è reindirizzato ovunque tranne
  `/personale/mio-lavoro/` (`apps/accounts/middleware.py`). Aggiungere pagine
  nuove per i collaboratori significa toccare lì.
- Template: `templates/<app>/...`, condivisi in `templates/partials/`, documenti
  stampabili in `templates/print/`. JS in `static/js/`.
- `billing`, `jobs` e `core` sono montati alla radice in `config/urls.py`
  (prefissi URL diversi da `apps/<app>/`).
- I file caricati si servono **solo** tramite `protected_media` in
  `config/urls.py` (login + `Content-Disposition: attachment` per i non inline).
  Non esporre `MEDIA_ROOT` altrove.

## Convenzioni

- Scrivere in italiano: stringhe della UI, `verbose_name`, docstring, commenti
  e messaggi di commit (`git log` è tutto in italiano).
- `DECIMAL_SEPARATOR = ","` / `THOUSAND_SEPARATOR = "."` negli importi.
- I test MCP (`apps/core/tests_mcp.py`) sono saltati se `mcp` non è installato:
  servono `requirements-mcp.txt`, che è volutamente **fuori** da
  `requirements.txt` (non serve in produzione).
- `README.md` è ampio e in parte invecchiato: la sezione "Struttura del
  progetto" **non elenca** `apps/leads` e `apps/gallery`, che invece sono in
  `INSTALLED_APPS`. Fidarsi del codice, non dell'elenco.

## Prima di toccare l'infrastruttura

`docs/sicurezza-e-backup.md` (operazioni VPS) e `scripts/backup.sh` /
`restore.sh` coprono backup, ripristino e hardening. `scripts/controllo_sito.sh`
fa il controllo del sito.
