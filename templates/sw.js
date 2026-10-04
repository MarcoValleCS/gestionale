/* Service worker del gestionale: cache degli asset statici e pagina offline. */
const CACHE_NAME = "gestionale-v3";
// Solo la pagina offline: gli asset statici si memorizzano da soli alla prima
// visita (i loro indirizzi cambiano a ogni versione, quindi non si possono
// elencare qui).
const PRECACHE = ["/offline/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Asset statici: si mostra subito la copia in cache e intanto si scarica
  // quella aggiornata, così una modifica al file si vede al ricaricamento
  // successivo (prima la copia vecchia restava per sempre).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          const aggiornata = fetch(request)
            .then((response) => {
              if (response && response.ok) cache.put(request, response.clone());
              return response;
            })
            .catch(() => cached);
          return cached || aggiornata;
        })
      )
    );
    return;
  }

  // Pagine: rete, con fallback offline quando non c'è connessione
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline/")));
  }
});
