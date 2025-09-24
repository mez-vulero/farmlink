// Farmlink Service Worker – Offline First
const CACHE = "farmlink-static-v1";
const offlineFallbackPage = "/assets/farmlink/offline.html";

importScripts("https://storage.googleapis.com/workbox-cdn/releases/5.1.2/workbox-sw.js");

// --- Install: precache essentials ---
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll([
        "/manifest.json",
        offlineFallbackPage,
        "/", // precache home page
        "/assets/farmlink/main.js", // example JS
        "/assets/farmlink/main.css", // example CSS
      ]);
    })
  );
  self.skipWaiting();
});

// --- Activate: cleanup old caches ---
self.addEventListener("activate", (event) => {
  const currentCaches = [CACHE, "api-cache-v1", "pages-cache-v1", "frappe-dist-cache", "farmlink-assets-cache", "image-cache", "static-assets"];
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames.map((cacheName) => {
          if (!currentCaches.includes(cacheName)) return caches.delete(cacheName);
        })
      )
    )
  );
  self.clients.claim();
});

// --- Enable navigation preload if available ---
if (self.workbox && workbox.navigationPreload.isSupported()) {
  workbox.navigationPreload.enable();
}

// --- API calls: NetworkFirst with cache and expiration ---
if (self.workbox) {
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith("/api/"),
    new workbox.strategies.NetworkFirst({
      cacheName: "api-cache-v1",
      networkTimeoutSeconds: 3,
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 24 * 60 * 60, // 1 day
        }),
        new workbox.cacheableResponse.CacheableResponsePlugin({
          statuses: [0, 200], // only cache successful responses
        }),
      ],
    })
  );

  // Frappe core bundles → CacheFirst
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith("/assets/frappe/dist/"),
    new workbox.strategies.CacheFirst({
      cacheName: "frappe-dist-cache",
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 200,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        }),
      ],
    })
  );

  // Farmlink app assets → CacheFirst
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith("/assets/farmlink/"),
    new workbox.strategies.CacheFirst({
      cacheName: "farmlink-assets-cache",
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 200,
          maxAgeSeconds: 30 * 24 * 60 * 60,
        }),
      ],
    })
  );

  // Scripts & styles (general) → CacheFirst
  workbox.routing.registerRoute(
    ({ request }) => ["script", "style"].includes(request.destination),
    new workbox.strategies.CacheFirst({
      cacheName: "static-assets",
    })
  );

  // Images → CacheFirst
  workbox.routing.registerRoute(
    ({ request }) => request.destination === "image",
    new workbox.strategies.CacheFirst({
      cacheName: "image-cache",
    })
  );

  // HTML documents → NetworkFirst with pages cache
  workbox.routing.registerRoute(
    ({ request }) => request.destination === "document",
    new workbox.strategies.NetworkFirst({
      cacheName: "pages-cache-v1",
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
        }),
      ],
    })
  );

  // Global catch → offline fallback for HTML
  workbox.routing.setCatchHandler(async ({ event }) => {
    if (event.request.destination === "document") {
      return caches.match(offlineFallbackPage);
    }
    return Response.error();
  });
}

// --- Extra fetch fallback for navigate requests ---
self.addEventListener("fetch", (event) => {
  if (event.request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const preloadResp = await event.preloadResponse;
          if (preloadResp) return preloadResp;

          return await fetch(event.request);
        } catch (error) {
          const cache = await caches.open(CACHE);
          return (await cache.match(offlineFallbackPage)) || Response.error();
        }
      })()
    );
  }
});

// --- Listen to messages from client to skip waiting ---
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

