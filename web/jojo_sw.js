// JoJo PWA Service Worker - Offline Support
const CACHE = "jojo-overlay-v1";
const ASSETS = ["/mobile_overlay", "/jojo_overlay_manifest.json", "/icons/jojo_icon_192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  // API calls - always network first
  if(e.request.url.includes("/api/")) return;
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).catch(() => cached))
  );
});
