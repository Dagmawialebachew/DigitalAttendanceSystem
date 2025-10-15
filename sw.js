const CACHE_NAME = 'iAttend-v1';
const urlsToCache = [
  '/static/css/app.css',
  '/static/icons/icon-192x192.png',
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.all(
        urlsToCache.map(url =>
          cache.add(url).catch(err => {
            console.warn(`❌ Failed to cache ${url}`, err);
          })
        )
      );
    })
  );
});
