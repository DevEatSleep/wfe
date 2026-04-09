const CACHE_NAME = 'assistant-financier-v1';
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/chatbot',
  '/static/css/chatbot.css',
  '/static/css/dashboard.css',
  '/static/manifest.json',
  '/static/icon.svg',
  '/static/icon-192.svg',
  '/static/icon-512.svg'
];

// Installation - cache les assets statiques
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Cache chaque asset individuellement pour éviter les erreurs
      return Promise.all(
        STATIC_ASSETS.map(asset => 
          cache.add(asset).catch(err => {
            console.warn(`Impossible de mettre en cache ${asset}:`, err);
          })
        )
      );
    })
  );
  self.skipWaiting();
});

// Activation - nettoie les anciens caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch - utilise le cache en priorité, puis réseau
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Pour les requêtes API, utiliser le réseau en priorité
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/chat')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Mettre en cache les réponses API réussies
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          // Si offline, servir depuis le cache ou une réponse par défaut
          return caches.match(request).catch(() => {
            return new Response(
              JSON.stringify({ error: 'Offline - données non disponibles' }),
              { status: 503, contentType: 'application/json' }
            );
          });
        })
    );
  } else {
    // Pour les assets statiques, cache-first strategy
    event.respondWith(
      caches.match(request).then(response => {
        if (response) {
          return response;
        }
        return fetch(request).then(response => {
          if (!response || response.status !== 200 || response.type === 'error') {
            return response;
          }
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, clone);
          });
          return response;
        }).catch(() => {
          // Fallback pour offline
          return new Response('Page non disponible', { status: 503 });
        });
      })
    );
  }
});

// Gestion des messages depuis le client
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
