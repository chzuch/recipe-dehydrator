/**
 * Service Worker：离线缓存应用壳 + 卡片数据 + 截图。
 * 策略：app 壳（页面/JS/CSS）precache；/api/cards 与截图 cache-first；
 * 其他 API 请求 network-first（打卡/置顶/编辑需要实时）。
 */
const CACHE = "vdh-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      cache.addAll([
        "/",
        "/static/css/app.css",
        "/static/dist/app.js",
        "/static/manifest.json",
      ]),
    ),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // 只处理同源 GET
  if (event.request.method !== "GET" || url.origin !== location.origin) return;

  // 卡片列表与截图：cache-first（离线可看）
  if (url.pathname === "/api/cards" || url.pathname.startsWith("/api/frames/")) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((resp) => {
            const copy = resp.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
            return resp;
          }),
      ),
    );
    return;
  }

  // 其余：network-first，失败回退缓存
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return resp;
      })
      .catch(() => caches.match(event.request)),
  );
});
