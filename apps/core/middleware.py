"""Protezioni di base contro abusi: tentativi di accesso e ricerca intensiva.

I contatori usano la cache condivisa (database), quindi il limite vale per
tutti i processi di gunicorn. Se la cache non è disponibile la richiesta
passa senza bloccare (fail-open), così un problema tecnico non chiude il
gestionale.
"""
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

LOGIN_PATHS = {"/accounts/login/", "/admin/login/"}
SEARCH_PREFIXES = ("/contatti/cerca/", "/articoli/cerca/")
SEARCH_PATTERNS = (
    re.compile(r"^/articoli/\d+/default/$"),
    re.compile(r"^/magazzino/articolo/\d+/giacenza/$"),
)


class AbuseThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rule = self.rule_for(request)
        if rule is not None:
            name, limit, window = rule
            if self.is_limited(request, name, limit, window):
                return self.too_many_requests(name)
        return self.get_response(request)

    # -------------------------------------------------------------- regole
    def rule_for(self, request):
        config = getattr(settings, "ABUSE_THROTTLE", {})
        if request.method == "POST" and request.path in LOGIN_PATHS:
            rule = config.get("login", {})
            return ("login", int(rule.get("limit", 8)), int(rule.get("window", 300)))
        if request.method == "GET" and self.is_search_path(request.path):
            rule = config.get("search", {})
            return ("search", int(rule.get("limit", 120)), int(rule.get("window", 60)))
        return None

    def is_search_path(self, path):
        return path.startswith(SEARCH_PREFIXES) or any(pattern.match(path) for pattern in SEARCH_PATTERNS)

    # ----------------------------------------------------------- conteggio
    def client_ip(self, request):
        """Indirizzo del client, per il conteggio dei tentativi.

        Dietro il proxy si prende l'**ultimo** indirizzo di ``X-Forwarded-For``:
        è quello aggiunto dal nostro proxy, quindi non falsificabile da chi fa
        la richiesta. Prendere il primo permetterebbe di aggirare il limite
        cambiando l'intestazione a ogni tentativo.
        """
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[-1].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")

    def is_limited(self, request, name, limit, window):
        key = f"throttle:{name}:{self.client_ip(request)}:{int(time.time()) // window}"
        try:
            if cache.add(key, 1, timeout=window):
                return False
            count = cache.incr(key)
        except Exception:
            return False
        return count > limit

    # ------------------------------------------------------------ risposta
    def too_many_requests(self, name):
        message = "Troppe richieste in poco tempo. Attendi qualche minuto e riprova."
        if name == "search":
            return JsonResponse({"error": message, "results": []}, status=429)
        return HttpResponse(f"<h1>429 — Troppe richieste</h1><p>{message}</p>", status=429, content_type="text/html; charset=utf-8")
