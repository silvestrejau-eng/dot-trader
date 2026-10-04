const CACHE='dot-trader-v1';
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/app/','/app/index.html','/app/manifest.json']))));
self.addEventListener('fetch',e=>{if(e.request.url.includes('/api/')) return; e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});
