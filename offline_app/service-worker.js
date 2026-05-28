const CACHE_NAME = "pharmareen-offline-v16-realpath-stock-safety";
console.log("OFFLINE_APP_BUILD_VERSION=realpath-stock-safety-v2026-05-28-1 service-worker");
const APP_SHELL = [
  "/offline-app",
  "/offline_app/index.html",
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
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request).then(response => response || caches.match("/offline-app"))));
});
