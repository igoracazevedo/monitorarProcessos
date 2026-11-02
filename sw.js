const CACHE_NAME = "iaz-jud-cache-v5";
// "./index.html" fica de fora: a Vercel redireciona para "./" (cleanUrls) e uma resposta
// redirecionada guardada no cache não pode ser usada para abrir o app instalado.
const ASSETS = [
  "./",
  "./manifest.json",
  "./icon.png",
  "./icon-192.png",
  "./icon-512.png",
  "./icon.svg"
];

// Instala o service worker e faz cache inicial (uma falha em um arquivo não impede a instalação)
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(ASSETS.map((a) => cache.add(a).catch(() => null)))
    )
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

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = req.url;
  // Supabase, DataJud e métodos não-GET vão direto para a rede
  if (url.includes("supabase.co") || url.includes("datajud.cnj.jus.br") || req.method !== "GET") {
    return;
  }

  // Abertura do app (navegação): rede primeiro; o cache serve só como reserva offline
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).catch(() => caches.match("./").then((r) => r || Response.error()))
    );
    return;
  }

  // Estáticos: cache primeiro
  e.respondWith(caches.match(req).then((cached) => cached || fetch(req)));
});
