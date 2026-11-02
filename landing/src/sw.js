// Service worker du site de présentation. Il ne gère que les ressources de ce site :
// GitHub et les paquets de PM² Desktop ne passent jamais par le cache.
const VERSION = "__VERSION__";
const CORE_CACHE = `pm2-site-core-${VERSION}`;
const ASSET_CACHE = `pm2-site-assets-${VERSION}`;
const PRECACHE = ["__PRECACHE__"];
const MAX_ASSETS = 40;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CORE_CACHE).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("pm2-site-") && key !== CORE_CACHE && key !== ASSET_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});

async function page(request) {
  try {
    const response = await fetch(request);
    const isHome = new URL(request.url).pathname === "/";
    if (response.ok && isHome) (await caches.open(CORE_CACHE)).put("/", response.clone());
    return response;
  } catch {
    const cached = new URL(request.url).pathname === "/" ? await caches.match("/") : undefined;
    return cached ?? caches.match("/offline");
  }
}

async function asset(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(ASSET_CACHE);
    await cache.put(request, response.clone());
    const keys = await cache.keys();
    if (keys.length > MAX_ASSETS) await cache.delete(keys[0]);
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (request.mode === "navigate") event.respondWith(page(request));
  else if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) event.respondWith(asset(request));
});
