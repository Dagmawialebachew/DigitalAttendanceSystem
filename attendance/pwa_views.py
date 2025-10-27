from django.http import JsonResponse, HttpResponse
from django.conf import settings


def manifest(request):
    manifest_data = {
        "name": "iAttend",
        "short_name": "iAttend",
        "description": "Modern 10-second code attendance system",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0ea5e9",
        "theme_color": "#0ea5e9",
        "orientation": "portrait",
        "icons": [
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return JsonResponse(manifest_data)


def service_worker(request):
    sw_content = """

const CACHE_NAME = 'iAttend-v1';
const urlsToCache = [
  'static/css/app.css',
  'static/icons/icon-192x192.png',
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
"""
    return HttpResponse(sw_content, content_type='application/javascript')
