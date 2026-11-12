/*
 * Notifications, loaded into the app's service worker (vite.config.ts → workbox.importScripts).
 * The server sends { title, body, url, tag } (backend/notifications/push.py). Tapping one opens that screen: in the app
 * if it's already open, otherwise in a new window.
 */
self.addEventListener('push', (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) { d = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(d.title || 'SpenDrip', {
    body: d.body || '',
    tag: d.tag || undefined,
    icon: '/icon-192.png',
    badge: '/badge-96.png',  // Android's status bar: white drop, shown on any colour
    data: { url: d.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const path = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    const open = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const app = open.find((c) => new URL(c.url).origin === self.location.origin);
    if (app) {
      app.postMessage({ type: 'sd-open', path });  // the app moves to that screen (see lib/push.ts)
      return app.focus();
    }
    return self.clients.openWindow(path);
  })());
});
