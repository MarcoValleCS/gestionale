"""Autenticazione a token per il server MCP esposto in rete.

In locale il server gira con trasporto stdio: chi lo avvia ha già il
controllo della macchina, non serve autenticazione. Quando il server viene
esposto via HTTP (in produzione, dietro Caddy) ogni chiamata deve invece
presentare un token Bearer valido: senza, chiunque potrebbe leggere e
scrivere i dati del gestionale.

I token si configurano dall'ambiente:

- ``MCP_TOKEN``: un token, valido per l'utente ``MCP_USER``;
- ``MCP_TOKENS``: elenco di coppie ``token:utente`` separate da virgola,
  utili quando più persone o più assistenti usano il gestionale: ogni
  chiamata resta attribuita a chi l'ha fatta.

Ogni token può avere uno scope (``token:utente:scope``): lo scope
``mcp:sola-lettura`` permette di consultare ma non di scrivere.

Il confronto dei token è sempre a tempo costante (``hmac.compare_digest``):
il tempo di risposta non deve dire quale token era quasi giusto.

Questo modulo non importa il pacchetto ``mcp``: così resta testabile anche
dove il pacchetto non è installato.
"""
import contextvars
import hmac
import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SCOPE_COMPLETO = "mcp"
SCOPE_SOLA_LETTURA = "mcp:sola-lettura"
SCOPES_CONOSCIUTI = (SCOPE_COMPLETO, SCOPE_SOLA_LETTURA)

# Rate limit di sicurezza: richieste al minuto per token. Il valore è
# generoso perché una sessione di lavoro può chiamare molti strumenti in
# sequenza: serve a fermare i cicli automatici, non a rallentare chi lavora.
RATE_LIMIT_PREDEFINITO = 300
# Finestra di memorizzazione delle richieste (secondi).
FINESTRA_RATE_LIMIT = 60


@dataclass(frozen=True)
class Credenziale:
    """Un token ammesso e l'utente a cui è attribuito."""

    token: str
    username: str
    scope: str = SCOPE_COMPLETO

    @property
    def sola_lettura(self) -> bool:
        return self.scope == SCOPE_SOLA_LETTURA


def _credenziale_da_testo(testo: str) -> Credenziale | None:
    """Converte «token:utente[:scope]» in una credenziale.

    Lo scope contiene lui stesso due punti («mcp:sola-lettura»): si divide
    quindi al massimo due volte, così la parte restante è lo scope intero.
    """
    parti = [p.strip() for p in (testo or "").split(":", 2)]
    if len(parti) < 2:
        return None
    token, username = parti[0], parti[1]
    scope = parti[2] if len(parti) > 2 else SCOPE_COMPLETO
    if not token or not username:
        return None
    if scope not in SCOPES_CONOSCIUTI:
        logger.warning("Scope MCP sconosciuto %r: uso %r.", scope, SCOPE_COMPLETO)
        scope = SCOPE_COMPLETO
    return Credenziale(token=token, username=username, scope=scope)


def carica_credenziali() -> list[Credenziale]:
    """Legge le credenziali dall'ambiente.

    ``MCP_TOKENS`` ha la precedenza su ``MCP_TOKEN``: sono due modi
    alternativi di dire la stessa cosa, non si sommano.
    """
    credenziali: list[Credenziale] = []
    elenco = (os.environ.get("MCP_TOKENS") or "").strip()
    if elenco:
        for pezzo in elenco.split(","):
            credenziale = _credenziale_da_testo(pezzo)
            if credenziale is None:
                logger.warning("Voce di MCP_TOKENS ignorata (formato atteso «token:utente»).")
                continue
            credenziali.append(credenziale)
        return credenziali
    token = (os.environ.get("MCP_TOKEN") or "").strip()
    if token:
        username = (os.environ.get("MCP_USER") or "").strip()
        if not username:
            logger.warning("MCP_TOKEN impostato ma MCP_USER vuoto: le scritture non saranno attribuite.")
        credenziali.append(Credenziale(token=token, username=username))
    return credenziali


def verifica_token(token: str) -> Credenziale | None:
    """Cerca il token fra quelli ammessi; ``None`` se non c'è."""
    if not token:
        return None
    for credenziale in carica_credenziali():
        if hmac.compare_digest(credenziale.token, token):
            return credenziale
    return None


def token_valido(token: str) -> bool:
    return verifica_token(token) is not None


def ip_ammessi() -> list[str]:
    """Elenco degli IP autorizzati (vuoto = nessun filtro per IP)."""
    grezzo = os.environ.get("MCP_ALLOWED_IPS") or ""
    return [ip.strip() for ip in grezzo.split(",") if ip.strip()]


def ip_consentito(indirizzo: str | None) -> bool:
    """True se l'IP è ammesso (o se non è impostata alcuna allowlist)."""
    ammessi = ip_ammessi()
    if not ammessi:
        return True
    if not indirizzo:
        return False
    return indirizzo in ammessi


def rate_limit_predefinito() -> int:
    """Richieste al minute ammesse per token (0 = senza limite)."""
    grezzo = (os.environ.get("MCP_RATE_LIMIT") or "").strip()
    if not grezzo:
        return RATE_LIMIT_PREDEFINITO
    try:
        return max(0, int(grezzo))
    except ValueError:
        logger.warning("MCP_RATE_LIMIT non valido (%r): uso %d.", grezzo, RATE_LIMIT_PREDEFINITO)
        return RATE_LIMIT_PREDEFINITO


class Limitatore:
    """Conta le richieste per token in una finestra di tempo scorrevole.

    Memoria sola, nel processo: se il server viene riavviato il conteggio
    riparte. Va bene per un VPS con una sola istanza.
    """

    def __init__(self, limite: int | None = None):
        self.limite = rate_limit_predefinito() if limite is None else limite
        self._conteggi: dict[str, list[float]] = {}

    def ammesso(self, chiave: str, adesso: float | None = None) -> bool:
        if self.limite <= 0:
            return True
        momento = time.monotonic() if adesso is None else adesso
        # ripulisce le voci vecchie: nessuna memoria residua
        for altro in list(self._conteggi):
            voci = [t for t in self._conteggi[altro] if momento - t < FINESTRA_RATE_LIMIT]
            if voci:
                self._conteggi[altro] = voci
            else:
                del self._conteggi[altro]
        voci = self._conteggi.setdefault(chiave, [])
        if len(voci) >= self.limite:
            return False
        voci.append(momento)
        return True


# --------------------------------------------------------------- contesto
# Credenziale della richiesta in corso: la imposta il middleware e la legge
# l'esecutore degli strumenti, così ogni scrittura resta attribuita.
credenziale_attuale: contextvars.ContextVar[Credenziale | None] = contextvars.ContextVar(
    "mcp_credenziale", default=None
)


def credenziale_corrente() -> Credenziale | None:
    """Credenziale della richiesta in corso (``None`` in locale, via stdio)."""
    return credenziale_attuale.get()


def solo_lettura() -> bool:
    """True se la richiesta in corso non può scrivere."""
    credenziale = credenziale_corrente()
    return bool(credenziale and credenziale.sola_lettura)


# --------------------------------------------------------------- middleware
def _ip_cliente(scope: dict) -> str | None:
    """IP reale del chiamante.

    Dietro Caddy l'IP vero arriva in ``X-Forwarded-For``: ci si fida perché
    il container del server MCP non è pubblicato e raggiungibile solo dalla
    rete interna di Docker.
    """
    for chiave, valore in scope.get("headers") or ():
        if chiave.lower() == b"x-forwarded-for":
            primo = valore.decode("latin-1").split(",")[0].strip()
            if primo:
                return primo
    cliente = scope.get("client")
    if cliente:
        return cliente[0]
    return None


def _token_da_headers(scope: dict) -> str:
    """Token Bearer della richiesta (vuoto se assente)."""
    for chiave, valore in scope.get("headers") or ():
        if chiave.lower() == b"authorization":
            testo = valore.decode("latin-1").strip()
            if testo.lower().startswith("bearer "):
                return testo[7:].strip()
            return ""
    return ""


async def _rispondi(send, stato: int, descrizione: str, extra: list[tuple[bytes, bytes]] | None = None):
    """Risposta di errore in formato JSON."""
    import json

    corpo = json.dumps({"error": descrizione}).encode()
    intestazioni = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(corpo)).encode()),
    ]
    if extra:
        intestazioni.extend(extra)
    await send({"type": "http.response.start", "status": stato, "headers": intestazioni})
    await send({"type": "http.response.body", "body": corpo})


class MiddlewareMcp:
    """Barriera davanti al server MCP esposto in rete.

    Nell'ordine: allowlist degli IP, token Bearer, rate limit. Chi supera i
    tre controlli entra nel server e ogni suo strumento viene attribuito
    all'utente del token.
    """

    def __init__(self, app, limitatore: Limitatore | None = None):
        self.app = app
        self.limitatore = limitatore if limitatore is not None else Limitatore()

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        indirizzo = _ip_cliente(scope)
        if not ip_consentito(indirizzo):
            logger.warning("Accesso MCP rifiutato: IP %s non ammesso.", indirizzo)
            await _rispondi(send, 403, "IP non ammesso")
            return

        token = _token_da_headers(scope)
        if not token:
            await _rispondi(
                send,
                401,
                "Autenticazione richiesta: header Authorization con token Bearer.",
                [(b"www-authenticate", b'Bearer realm="gestionale"')],
            )
            return

        credenziale = verifica_token(token)
        if credenziale is None:
            logger.warning("Accesso MCP rifiutato: token non valido (IP %s).", indirizzo)
            await _rispondi(
                send,
                401,
                "Token non valido.",
                [(b"www-authenticate", b'Bearer realm="gestionale", error="invalid_token"')],
            )
            return

        if not self.limitatore.ammesso(credenziale.username):
            logger.warning("Accesso MCP rifiutato: troppe richieste per %s.", credenziale.username)
            await _rispondi(send, 429, "Troppe richieste: riprova fra poco.")
            return

        segnaposto = credenziale_attuale.set(credenziale)
        try:
            await self.app(scope, receive, send)
        finally:
            credenziale_attuale.reset(segnaposto)
