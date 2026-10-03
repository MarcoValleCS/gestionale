/* Service worker del gestionale: cache degli asset statici e pagina offline. */
const CACHE_NAME = "gestionale-v2";
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

  // Asset statici: prima la cache, poi la rete
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            return response;
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
