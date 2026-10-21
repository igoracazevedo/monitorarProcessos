const CACHE_NAME = "iaz-jud-cache-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon.png",
  "./icon.svg"
];

// Instala o service worker e faz cache inicial
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Ativa e limpa versões antigas do cache
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => k !== CACHE_NAME && caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first para chamadas à API REST (Supabase e DataJud), cache-first para estáticos
self.addEventListener("fetch", (e) => {
  const url = e.request.url;
  if (url.includes("supabase.co") || url.includes("datajud.cnj.jus.br") || e.request.method !== "GET") {
    return; // Passa direto para a rede sem cachear dados dinâmicos do banco
  }

  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      return (
        cachedResponse ||
        fetch(e.request).then((networkResponse) => {
          return networkResponse;
        })
      );
    })
  );
});
