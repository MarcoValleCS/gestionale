"""Costruzione dell'applicazione HTTP del server MCP (per la produzione).

Il server esposto in rete passa da qui: un'applicazione Starlette con la
protezione DNS rebinding attiva e il middleware di autenticazione di
``mcp_auth`` davanti a tutto. Ogni richiesta deve portare un token Bearer
valido: chi non ce l'ha non entra, e le scritture restano attribuite
all'utente del token.

Il trasporto è «senza stato»: ogni richiesta è autosufficiente e autenticata,
niente sessioni da tenere in memoria e nessuna sessione che sopravvive al
token con cui è stata aperta.
"""
import os


def domini_ammessi() -> tuple[list[str], list[str]]:
    """Host e origini ammessi (protezione DNS rebinding).

    Il server accetta richieste solo se dichiariamo da dove arrivano: senza
    questa lista un sito qualsiasi potrebbe pilotare il gestionale dal
    browser di chi lo visita (attacco DNS rebinding).
    """
    domini = [d.strip() for d in (os.environ.get("MCP_ALLOWED_HOSTS") or "").split(",") if d.strip()]
    if not domini:
        dominio = (os.environ.get("DOMAIN") or "").strip()
        if dominio:
            domini = [dominio]
    origini = [o.strip() for o in (os.environ.get("MCP_ALLOWED_ORIGINS") or "").split(",") if o.strip()]
    if not origini and domini:
        origini = [f"https://{domini[0]}"]
    hosts: list[str] = []
    for dominio in domini:
        hosts.append(dominio)
        hosts.append(f"{dominio}:*")
    return hosts, origini


def applicazione_http():
    """Crea l'applicazione Starlette pronta per il trasporto HTTP."""
    from mcp.server.fastmcp.server import TransportSecuritySettings

    from mcp_auth import MiddlewareMcp, carica_credenziali
    from mcp_common import mcp

    if not carica_credenziali():
        raise RuntimeError(
            "MCP: nessun token configurato. Imposta MCP_TOKEN (e MCP_USER) "
            "oppure MCP_TOKENS nel file .env prima di avviare il server HTTP."
        )

    hosts, origini = domini_ammessi()
    if not hosts:
        raise RuntimeError(
            "MCP: indica gli host ammessi con MCP_ALLOWED_HOSTS (oppure DOMAIN): "
            "senza questa protezione il server non si avvia."
        )

    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origini,
    )
    mcp.settings.stateless_http = True

    # Il gestore delle sessioni viene creato alla prima richiesta e può essere
    # avviato una volta sola: se ne creo uno nuovo, ogni applicazione ha il
    # suo (e riavviare il server non lascia mezzo stato indietro).
    mcp._session_manager = None  # noqa: SLF001 - dettaglio interno della libreria

    app = mcp.streamable_http_app()
    # Il middleware va aggiunto per ultimo: così è il più esterno e vede ogni
    # richiesta prima che arrivi al server MCP.
    app.add_middleware(MiddlewareMcp)
    return app
