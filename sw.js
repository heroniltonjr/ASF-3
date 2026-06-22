const CACHE_NAME = 'formula-os-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/atendimento.html',
  '/app.js',
  '/styles.css',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // Ignora requisições de API, apenas estáticos no cache-first
  if (event.request.method !== 'GET' || event.request.url.includes('/api/')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request).then(fetchRes => {
        // Atualiza o cache de forma preguiçosa se for recurso da mesma origem e GET
        if (fetchRes && fetchRes.status === 200 && fetchRes.type === 'basic') {
          const responseToCache = fetchRes.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return fetchRes;
      });
    }).catch(() => {
      // Offline fallback para páginas HTML
      if (event.request.mode === 'navigate') {
        return caches.match('/atendimento.html');
      }
    })
  );
});

// Handling Web Push Events
self.addEventListener('push', event => {
  let data = { title: 'Nova Notificação', body: 'Você tem uma nova mensagem.' };
  
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    console.error('Erro ao fazer parse do evento push', e);
  }
  
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/assets/icon-192.png',
      badge: '/assets/icon-192.png',
      data: data.url || '/atendimento.html',
      vibrate: [200, 100, 200]
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data;
  if (url) {
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then(windowClients => {
        // Se a janela já estiver aberta, foca nela e navega
        for (let i = 0; i < windowClients.length; i++) {
          let client = windowClients[i];
          if (client.url.includes(url) && 'focus' in client) {
            return client.focus();
          }
        }
        // Senão abre uma nova janela
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
    );
  }
});
