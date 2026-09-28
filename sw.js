const CACHE_NAME = "processos-cache-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json"
];

// Instala o service worker e faz cache da interface
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

// Responde com cache se offline; requisições para a API do DataJud vão sempre na rede
self.addEventListener("fetch", (e) => {
  if (e.request.url.includes("datajud.cnj.jus.br")) {
    return; // Não intercepta chamadas à API
  }
  e.respondWith(
    caches.match(e.request).then((res) => res || fetch(e.request))
  );
});
