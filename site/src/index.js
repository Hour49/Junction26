// junction.hour49.com: the clickable Vellum demo, the static assets build-assets.sh makes, with a strip at the top of
// every page that links to the credits the drawings' licences ask for. The full app is offline for good (Bogdan,
// 2026-11-17: "I only want the clicky html demo to work, I won't keep the main app live"), so there is no access code,
// no secret and no proxy: the old code links go back to the demo and /api/* says the app is offline.

// a strip above the demo page, in its flow: a fixed box in a corner covered the demo's own buttons
const STRIP =
  `<div style="margin:0;padding:6px 12px;background:#fff;color:#111;border-bottom:1px solid #ccc;` +
  `font:14px/1.3 system-ui,sans-serif"><a href="/credits.html" style="color:inherit">Credits</a></div>`;

// the access code's form and its sign-out link, from before 2026-11-17
const OLD_LINKS = new Set(["/__unlock", "/__lock"]);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (OLD_LINKS.has(url.pathname)) {
      return new Response(null, { status: 303, headers: { location: "/" } });
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
    }
    if (url.pathname.startsWith("/api/")) {
      return Response.json({ error: "the full app is offline; this site is a click-through demo" }, { status: 410 });
    }
    const asset = await env.ASSETS.fetch(request);
    const type = asset.headers.get("content-type") || "";
    if (request.method === "GET" && asset.ok && type.includes("text/html")) {
      const html = await asset.text();
      const body = /<body[^>]*>/i;
      const out = new Response(body.test(html) ? html.replace(body, (tag) => tag + STRIP) : STRIP + html, asset);
      out.headers.delete("content-length");
      out.headers.delete("etag"); // the asset's etag is for the page without the strip
      return out;
    }
    return asset;
  },
};
