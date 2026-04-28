const CACHE_NAME = "cf-checklist-frota-pwa-20260428-07";
const STATIC_CACHE_PATHS = [
    "./manifest.json",
    "./static/icons/icon-192.png",
    "./static/icons/icon-512.png",
    "./static/icons/cf-logo-mark.png",
    "./static/icons/cf-logo-cover.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(STATIC_CACHE_PATHS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys
                .filter((key) => key !== CACHE_NAME)
                .map((key) => caches.delete(key))))
    );
});

self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);

    if (request.method !== "GET" || url.origin !== self.location.origin) {
        return;
    }

    const isAppCode = url.pathname.endsWith(".html")
        || url.pathname.endsWith(".css")
        || url.pathname.endsWith(".js")
        || request.mode === "navigate";

    if (isAppCode) {
        event.respondWith(
            fetch(request, { cache: "no-store" })
                .then((response) => {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                    return response;
                })
                .catch(() => caches.match(request))
        );
        return;
    }

    event.respondWith(
        caches.match(request)
            .then((cached) => cached || fetch(request).then((response) => {
                if (response.ok) {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                }
                return response;
            }))
    );
});
