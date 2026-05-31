const CACHE_NAME = "pharmareen-offline-v25-phone-ready";
const OFFLINE_INDEX = "/offline_app/index.html";
const MEDICINE_INDEX = "/offline/medicine-names";
console.log("OFFLINE_APP_BUILD_VERSION=kenya-medicine-brain-v2026-05-31-phone-ready service-worker");
const APP_SHELL = [
  OFFLINE_INDEX,
  "/offline_app/parser.js",
  "/offline_app/app.js",
  "/offline_app/styles.css",
  "/offline_app/manifest.json",
  "/offline_app/icon.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      await cache.addAll(APP_SHELL);
      try {
        const response = await fetch(MEDICINE_INDEX, { cache: "no-store" });
        if (response.ok) await cache.put(MEDICINE_INDEX, response);
      } catch {
        // The selector still uses the last safe medicine list stored on this phone.
      }
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(OFFLINE_INDEX, { ignoreSearch: true }))
    );
    return;
  }
  if (new URL(event.request.url).pathname === MEDICINE_INDEX) {
    const refresh = fetch(event.request)
      .then(async response => {
        if (response.ok) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put(MEDICINE_INDEX, response.clone());
        }
        return response;
      });
    event.waitUntil(refresh.catch(() => undefined));
    event.respondWith(
      caches.match(MEDICINE_INDEX, { ignoreSearch: true })
        .then(cached => cached || refresh)
        .catch(() => refresh)
    );
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request, { ignoreSearch: true }))
  );
});
