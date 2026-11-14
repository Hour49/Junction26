// junction.hour49.com: a shared access code in front of the real app. No valid cookie: the HTML demo (static
// assets) and a small "Have an access code?" form. The right code sets a signed 24 h cookie; with it every request
// is proxied to the tunnel origin, which is only reachable with the Cloudflare Access service token this Worker adds.
//
// Secrets (wrangler secret put): ACCESS_CODE, COOKIE_KEY, ORIGIN_URL, ACCESS_CLIENT_ID, ACCESS_CLIENT_SECRET.
// With ACCESS_CODE or COOKIE_KEY missing nothing unlocks (fail closed).

import { COOKIE, TTL_S, codeMatches, cookieValue, setCookie, sign, verify, withoutCookie } from "./gate.js";

const FORM_STYLE =
  "position:fixed;right:12px;bottom:12px;z-index:2147483647;background:#fff;color:#111;border:1px solid #bbb;" +
  "border-radius:8px;padding:8px 10px;font:14px/1.3 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.2)";

const FORM =
  `<form method="post" action="/__unlock" style="${FORM_STYLE}"><label>Have an access code? ` +
  `<input name="code" type="password" autocomplete="off" required style="font:inherit;width:11em"></label> ` +
  `<button type="submit" style="font:inherit">Open the app</button></form>`;

// what Cloudflare or the local server answers when the tunnel or the backend is down
const OFFLINE = new Set([502, 503, 530]);

function page(body, status = 200) {
  const html =
    `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<title>Access code</title><body style="font:16px/1.5 system-ui,sans-serif;max-width:30em;margin:3em auto;padding:0 1em">${body}`;
  return new Response(html, {
    status,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

function unlockPage(message) {
  const note = message ? `<p><strong>${message}</strong></p>` : "";
  return page(
    `<h1>Access code</h1>${note}<form method="post" action="/__unlock"><p><input name="code" type="password" ` +
      `autocomplete="off" autofocus required> <button type="submit">Open the app</button></p></form>` +
      `<p><a href="/">Back to the demo</a></p>`,
    message ? 401 : 200,
  );
}

async function isUnlocked(request, env) {
  if (!env.COOKIE_KEY) return false;
  const value = cookieValue(request.headers.get("cookie"), COOKIE);
  return value !== null && (await verify(env.COOKIE_KEY, value, Math.floor(Date.now() / 1000)));
}

async function unlock(request, env) {
  if (!env.ACCESS_CODE || !env.COOKIE_KEY) return page("<p>The access code is not set up.</p>", 503);
  let given = "";
  try {
    given = String((await request.formData()).get("code") ?? "");
  } catch {
    // not a form: no code
  }
  if (!(await codeMatches(env.ACCESS_CODE, given))) return unlockPage("That code is not right.");
  const expires = Math.floor(Date.now() / 1000) + TTL_S;
  return new Response(null, {
    status: 303,
    headers: {
      location: "/",
      "set-cookie": setCookie(await sign(env.COOKIE_KEY, expires), TTL_S),
      "cache-control": "no-store",
    },
  });
}

async function proxy(request, env) {
  if (!env.ORIGIN_URL || !env.ACCESS_CLIENT_ID || !env.ACCESS_CLIENT_SECRET) {
    return page("<p>The app is not connected.</p>", 503);
  }
  const url = new URL(request.url);
  // set the path on the origin's URL: resolving "//other.host/x" against it would send the token to other.host
  const target = new URL(env.ORIGIN_URL);
  target.pathname = url.pathname;
  target.search = url.search;
  const wantsPage = request.method === "GET" && (request.headers.get("accept") || "").includes("text/html");
  const headers = new Headers(request.headers);
  const rest = withoutCookie(headers.get("cookie"), COOKIE); // the gate cookie never leaves this Worker
  if (rest) headers.set("cookie", rest);
  else headers.delete("cookie");
  headers.set("cf-access-client-id", env.ACCESS_CLIENT_ID);
  headers.set("cf-access-client-secret", env.ACCESS_CLIENT_SECRET);
  headers.set("x-forwarded-host", url.host);
  headers.set("x-forwarded-proto", "https");
  const bodiless = request.method === "GET" || request.method === "HEAD";
  let reply = null;
  try {
    reply = await fetch(
      new Request(target, {
        method: request.method,
        headers,
        body: bodiless ? undefined : request.body,
        redirect: "manual",
        duplex: "half",
      }),
    );
  } catch {
    // the origin did not answer
  }
  if (wantsPage && (!reply || OFFLINE.has(reply.status))) {
    return page(
      `<h1>The app is offline right now</h1><p>It runs on one machine, and that machine is not answering. ` +
        `Try again in a minute.</p><p><a href="/__lock">See the demo instead</a></p>`,
      503,
    );
  }
  if (!reply) return Response.json({ error: "the app is offline" }, { status: 502 });
  const out = new Response(reply.body, reply);
  const location = reply.headers.get("location");
  if (location && location.startsWith(target.origin)) {
    out.headers.set("location", url.origin + location.slice(target.origin.length));
  }
  // "/" is the demo without the cookie and the app with it: a stored page would show the wrong one
  if ((reply.headers.get("content-type") || "").includes("text/html")) out.headers.set("cache-control", "no-store");
  return out;
}

async function demo(request, env) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
  }
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) {
    return Response.json({ error: "an access code is needed for the app" }, { status: 401 });
  }
  const asset = await env.ASSETS.fetch(request);
  const type = asset.headers.get("content-type") || "";
  if (request.method === "GET" && asset.ok && type.includes("text/html")) {
    const html = await asset.text();
    const out = new Response(html.includes("</body>") ? html.replace("</body>", `${FORM}</body>`) : html + FORM, asset);
    out.headers.delete("content-length");
    out.headers.delete("etag");
    out.headers.set("cache-control", "no-store"); // see proxy(): the same address is the app once unlocked
    return out;
  }
  return asset;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/__unlock") {
      if (request.method === "POST") return unlock(request, env);
      return unlockPage("");
    }
    if (url.pathname === "/__lock") {
      return new Response(null, {
        status: 303,
        headers: { location: "/", "set-cookie": setCookie("", 0), "cache-control": "no-store" },
      });
    }
    return (await isUnlocked(request, env)) ? proxy(request, env) : demo(request, env);
  },
};
