const CACHE_NAME = "pharmareen-offline-v23-voice-card";
const OFFLINE_INDEX = "/offline_app/index.html";
console.log("OFFLINE_APP_BUILD_VERSION=kenya-medicine-brain-v2026-05-31-voice-card service-worker");
const APP_SHELL = [
  OFFLINE_INDEX,
  "/offline_app/parser.js",
  "/offline_app/app.js",
  "/offline_app/styles.css",
  "/offline_app/manifest.json",
  "/offline_app/icon.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
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
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request, { ignoreSearch: true }))
  );
});
