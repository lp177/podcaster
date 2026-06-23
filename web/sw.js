/* Service worker — app-shell caching + offline audio playback. */
const SHELL = "pdj-shell-v2"
const AUDIO = "pdj-audio"
const CDN = "pdj-cdn-v2"
const SHELL_FILES = ["/", "/styles.css", "/app.js", "/manifest.webmanifest", "/favicon.svg", "/icon-192.png", "/share.html"]

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()))
})

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => ![SHELL, AUDIO, CDN].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener("fetch", (e) => {
  const req = e.request
  if (req.method !== "GET") return
  const url = new URL(req.url)
  const sameOrigin = url.origin === location.origin

  // API calls are always live — never cached.
  if (sameOrigin && url.pathname.startsWith("/api/")) return

  // Audio: cache-first so episodes saved for offline keep playing without network.
  if (sameOrigin && url.pathname.startsWith("/media/")) {
    e.respondWith(
      caches.open(AUDIO).then(async (c) => {
        const hit = await c.match(req)
        if (hit) return hit
        try {
          return await fetch(req)
        } catch (_) {
          return new Response("", { status: 504, statusText: "Offline" })
        }
      })
    )
    return
  }

  // Navigations: network-first, fall back to the cached app shell when offline.
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match(req).then((r) => r || caches.match("/"))))
    return
  }

  // Static assets + the Vue CDN bundle: stale-while-revalidate.
  if (sameOrigin || url.origin === "https://unpkg.com") {
    const name = sameOrigin ? SHELL : CDN
    e.respondWith(
      caches.open(name).then(async (c) => {
        const hit = await c.match(req)
        const net = fetch(req)
          .then((res) => {
            if (res && res.status === 200) c.put(req, res.clone())
            return res
          })
          .catch(() => hit)
        return hit || net
      })
    )
  }
})
