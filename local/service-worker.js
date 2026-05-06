const CACHE_NAME = "pharmareen-offline-v1";
const ASSETS = ["/offline_app/index.html", "/offline_app/offline.js", "/offline_app/manifest.json"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
});

self.addEventListener("fetch", event => {
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
