import assert from "node:assert/strict";
import { test } from "node:test";

import { COOKIE, TTL_S, codeMatches, cookieValue, setCookie, sign, verify, withoutCookie } from "../src/gate.js";
import worker from "../src/index.js";

const KEY = "test-cookie-key-not-a-secret";
const CODE = "abcd-efgh-jklm-npqr";
const ORIGIN = "https://origin.example.test";
const now = () => Math.floor(Date.now() / 1000);

const env = (extra = {}) => ({
  ACCESS_CODE: CODE,
  COOKIE_KEY: KEY,
  ORIGIN_URL: ORIGIN,
  ACCESS_CLIENT_ID: "client-id-x",
  ACCESS_CLIENT_SECRET: "client-secret-x",
  ASSETS: {
    fetch: async (request) => {
      const { pathname } = new URL(request.url);
      if (pathname === "/" || pathname === "/mock/index.html") {
        return new Response("<html><body><h1>demo</h1></body></html>", { headers: { "content-type": "text/html" } });
      }
      if (pathname === "/style.css") return new Response("a{}", { headers: { "content-type": "text/css" } });
      return new Response("not found", { status: 404 });
    },
  },
  ...extra,
});

async function cookieFor(secret = KEY, expires = now() + 600) {
  return `${COOKIE}=${await sign(secret, expires)}`;
}

function formRequest(code, path = "/__unlock") {
  return new Request(`https://junction.example.test${path}`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ code }),
  });
}

// the origin: records what it was sent
function fakeOrigin(reply = () => new Response("from the app", { status: 200 })) {
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (request) => {
    seen.push({
      url: request.url,
      method: request.method,
      headers: request.headers,
      body: request.body ? await request.text() : "",
      redirect: request.redirect,
    });
    return reply(request);
  };
  return { seen, restore: () => (globalThis.fetch = original) };
}

test("a cookie signed with the key verifies until it expires", async () => {
  const value = await sign(KEY, now() + 60);
  assert.equal(await verify(KEY, value, now()), true);
  assert.equal(await verify(KEY, value, now() + 61), false); // expired
  assert.equal(await verify(KEY, await sign(KEY, now() - 1), now()), false);
});

test("a cookie of another key, a changed expiry or a damaged value does not verify", async () => {
  const value = await sign(KEY, now() + 60);
  assert.equal(await verify("another-key", value, now()), false);
  const [v, , mac] = value.split(".");
  assert.equal(await verify(KEY, `${v}.${now() + 999999}.${mac}`, now()), false); // expiry stretched
  assert.equal(await verify(KEY, `${value}x`, now()), false);
  for (const bad of ["", "v1", "v1.1.2.3", "v2.9999999999.abc", "v1.abc.def", "v1.9999999999.", "v1.9999999999.!!!"]) {
    assert.equal(await verify(KEY, bad, now()), false, bad);
  }
  assert.equal(await verify("", value, now()), false);
  assert.equal(await verify(KEY, undefined, now()), false);
});

test("the code check takes the right code and nothing else", async () => {
  assert.equal(await codeMatches(CODE, CODE), true);
  assert.equal(await codeMatches(CODE, `  ${CODE}\n`), true); // pasted with spaces
  for (const wrong of ["", "abcd-efgh-jklm-npqx", CODE.toUpperCase(), CODE + "x", "abcd", undefined, null]) {
    assert.equal(await codeMatches(CODE, wrong), false, String(wrong));
  }
  assert.equal(await codeMatches("", ""), false); // no code set: never matches
  assert.equal(await codeMatches(undefined, "x"), false);
});

test("cookie helpers: read, strip, and the flags of the gate cookie", () => {
  assert.equal(cookieValue(`a=1; ${COOKIE}=xyz; b=2`, COOKIE), "xyz");
  assert.equal(cookieValue("a=1", COOKIE), null);
  assert.equal(cookieValue(null, COOKIE), null);
  assert.equal(withoutCookie(`a=1; ${COOKIE}=xyz; b=2`, COOKIE), "a=1; b=2");
  assert.equal(withoutCookie(`${COOKIE}=xyz`, COOKIE), null);
  const set = setCookie("v", TTL_S);
  for (const flag of ["HttpOnly", "Secure", "SameSite=Lax", "Path=/", "Max-Age=86400"]) assert.ok(set.includes(flag), flag);
});

test("no cookie: the demo with the code form; the app's API is refused", async () => {
  const demo = await worker.fetch(new Request("https://junction.example.test/"), env());
  assert.equal(demo.status, 200);
  const html = await demo.text();
  assert.ok(html.includes("<h1>demo</h1>") && html.includes("Have an access code?") && html.includes('action="/__unlock"'));
  const css = await worker.fetch(new Request("https://junction.example.test/style.css"), env());
  assert.equal(await css.text(), "a{}"); // assets other than pages are untouched
  const api = await worker.fetch(new Request("https://junction.example.test/api/projects"), env());
  assert.equal(api.status, 401);
});

test("no cookie: nothing reaches the origin, and only GET and HEAD reach the demo", async () => {
  const origin = fakeOrigin();
  try {
    for (const method of ["POST", "PUT", "DELETE"]) {
      const answer = await worker.fetch(
        new Request("https://junction.example.test/api/projects", { method, body: "x" }),
        env(),
      );
      assert.ok([401, 405].includes(answer.status), `${method} ${answer.status}`);
    }
    const post = await worker.fetch(new Request("https://junction.example.test/", { method: "POST", body: "x" }), env());
    assert.equal(post.status, 405);
    assert.equal(origin.seen.length, 0);
  } finally {
    origin.restore();
  }
});

test("a wrong code gives 401 and no cookie; the right code gives a signed cookie and a redirect to the app", async () => {
  const wrong = await worker.fetch(formRequest("nope"), env());
  assert.equal(wrong.status, 401);
  assert.equal(wrong.headers.get("set-cookie"), null);
  const empty = await worker.fetch(formRequest(""), env());
  assert.equal(empty.status, 401);
  const right = await worker.fetch(formRequest(CODE), env());
  assert.equal(right.status, 303);
  assert.equal(right.headers.get("location"), "/");
  const set = right.headers.get("set-cookie");
  for (const flag of ["HttpOnly", "Secure", "SameSite=Lax", "Max-Age=86400"]) assert.ok(set.includes(flag), flag);
  const value = cookieValue(set, COOKIE);
  assert.equal(await verify(KEY, value, now()), true);
  assert.equal(await verify(KEY, value, now() + TTL_S + 5), false); // 24 h and no longer
  assert.ok(!set.includes(CODE) && !set.includes(KEY)); // the cookie holds neither secret
});

test("a body that is not a form is a wrong code, not an error", async () => {
  const answer = await worker.fetch(
    new Request("https://junction.example.test/__unlock", { method: "POST", body: "{not a form" }),
    env(),
  );
  assert.equal(answer.status, 401);
});

test("with no code or no key set, nothing unlocks, and a cookie made with any key is not accepted when the key is unset", async () => {
  const noCode = await worker.fetch(formRequest(CODE), env({ ACCESS_CODE: "" }));
  assert.equal(noCode.status, 503);
  const noKey = await worker.fetch(formRequest(CODE), env({ COOKIE_KEY: "" }));
  assert.equal(noKey.status, 503);
  const origin = fakeOrigin();
  try {
    const forged = await sign("x", now() + 600);
    const got = await worker.fetch(
      new Request("https://junction.example.test/api/x", { headers: { cookie: `${COOKIE}=${forged}` } }),
      env({ COOKIE_KEY: "" }),
    );
    assert.equal(got.status, 401);
    assert.equal(origin.seen.length, 0);
  } finally {
    origin.restore();
  }
});

test("an expired or foreign cookie gets the demo, not the app", async () => {
  const origin = fakeOrigin();
  try {
    for (const cookie of [await cookieFor(KEY, now() - 5), await cookieFor("other-key")]) {
      const answer = await worker.fetch(
        new Request("https://junction.example.test/", { headers: { cookie } }),
        env(),
      );
      assert.ok((await answer.text()).includes("<h1>demo</h1>"));
    }
    assert.equal(origin.seen.length, 0);
  } finally {
    origin.restore();
  }
});

test("a valid cookie proxies the request: method, path, query, headers and body reach the origin", async () => {
  const origin = fakeOrigin((request) => new Response("made", { status: 202, headers: { "x-from": "app" } }));
  try {
    const request = new Request("https://junction.example.test/api/projects?name=a.zip&x=1", {
      method: "POST",
      headers: {
        cookie: `other=1; ${await cookieFor()}; theme=dark`,
        "content-type": "application/zip",
        "x-custom": "kept",
      },
      body: "zip-bytes",
    });
    const answer = await worker.fetch(request, env());
    assert.equal(answer.status, 202);
    assert.equal(await answer.text(), "made");
    assert.equal(answer.headers.get("x-from"), "app");
    const [sent] = origin.seen;
    assert.equal(sent.url, `${ORIGIN}/api/projects?name=a.zip&x=1`);
    assert.equal(sent.method, "POST");
    assert.equal(sent.body, "zip-bytes");
    assert.equal(sent.headers.get("content-type"), "application/zip");
    assert.equal(sent.headers.get("x-custom"), "kept");
    assert.equal(sent.headers.get("cf-access-client-id"), "client-id-x");
    assert.equal(sent.headers.get("cf-access-client-secret"), "client-secret-x");
    assert.equal(sent.headers.get("x-forwarded-host"), "junction.example.test");
    assert.equal(sent.redirect, "manual");
  } finally {
    origin.restore();
  }
});

test("the gate cookie never reaches the origin; other cookies do", async () => {
  const origin = fakeOrigin();
  try {
    const gate = await cookieFor();
    await worker.fetch(
      new Request("https://junction.example.test/", { headers: { cookie: `a=1; ${gate}; b=2` } }),
      env(),
    );
    await worker.fetch(new Request("https://junction.example.test/", { headers: { cookie: gate } }), env());
    assert.equal(origin.seen[0].headers.get("cookie"), "a=1; b=2");
    assert.equal(origin.seen[1].headers.get("cookie"), null);
    for (const sent of origin.seen) assert.ok(!JSON.stringify([...sent.headers]).includes(KEY));
  } finally {
    origin.restore();
  }
});

test("a visitor cannot send the Access service-token headers themselves", async () => {
  const origin = fakeOrigin();
  try {
    await worker.fetch(
      new Request("https://junction.example.test/", {
        headers: { cookie: await cookieFor(), "cf-access-client-id": "evil", "cf-access-client-secret": "evil" },
      }),
      env(),
    );
    assert.equal(origin.seen[0].headers.get("cf-access-client-id"), "client-id-x");
    assert.equal(origin.seen[0].headers.get("cf-access-client-secret"), "client-secret-x");
  } finally {
    origin.restore();
  }
});

test("a redirect to the origin's own address is sent back as the public address", async () => {
  const origin = fakeOrigin(() => new Response(null, { status: 307, headers: { location: `${ORIGIN}/api/projects/` } }));
  try {
    const answer = await worker.fetch(
      new Request("https://junction.example.test/api/projects", { headers: { cookie: await cookieFor() } }),
      env(),
    );
    assert.equal(answer.status, 307);
    assert.equal(answer.headers.get("location"), "https://junction.example.test/api/projects/");
  } finally {
    origin.restore();
  }
});

test("an unlocked visitor with no origin set gets 503, not a request to nowhere", async () => {
  const origin = fakeOrigin();
  try {
    const answer = await worker.fetch(
      new Request("https://junction.example.test/", { headers: { cookie: await cookieFor() } }),
      env({ ORIGIN_URL: "" }),
    );
    assert.equal(answer.status, 503);
    assert.equal(origin.seen.length, 0);
  } finally {
    origin.restore();
  }
});

test("locking clears the cookie", async () => {
  const answer = await worker.fetch(new Request("https://junction.example.test/__lock"), env());
  assert.equal(answer.status, 303);
  assert.ok(answer.headers.get("set-cookie").includes("Max-Age=0"));
});

test("a path that looks like another host still goes to the origin, never anywhere else", async () => {
  const origin = fakeOrigin();
  try {
    await worker.fetch(
      new Request("https://junction.example.test//evil.example.test/steal?x=1", { headers: { cookie: await cookieFor() } }),
      env(),
    );
    const [sent] = origin.seen;
    assert.equal(new URL(sent.url).origin, ORIGIN); // the service token goes only to the origin
    assert.equal(sent.url, `${ORIGIN}//evil.example.test/steal?x=1`);
  } finally {
    origin.restore();
  }
});

test("pages are never stored by the browser: the same address is the demo or the app, by cookie", async () => {
  const demo = await worker.fetch(new Request("https://junction.example.test/"), env());
  assert.equal(demo.headers.get("cache-control"), "no-store");
  const origin = fakeOrigin((request) =>
    new URL(request.url).pathname === "/"
      ? new Response("<html>app</html>", { headers: { "content-type": "text/html", "last-modified": "Sat, 14 Nov 2026 10:00:00 GMT" } })
      : new Response("js", { headers: { "content-type": "text/javascript", "cache-control": "max-age=600" } }),
  );
  try {
    const cookie = await cookieFor();
    const app = await worker.fetch(new Request("https://junction.example.test/", { headers: { cookie } }), env());
    assert.equal(await app.text(), "<html>app</html>");
    assert.equal(app.headers.get("cache-control"), "no-store");
    const script = await worker.fetch(new Request("https://junction.example.test/assets/a.js", { headers: { cookie } }), env());
    assert.equal(script.headers.get("cache-control"), "max-age=600"); // other files keep the app's own caching
  } finally {
    origin.restore();
  }
});

test("the app offline: a page that says so with the way back to the demo; API calls get JSON", async () => {
  const cookie = await cookieFor();
  const page = { cookie, accept: "text/html,application/xhtml+xml" };
  for (const reply of [() => new Response("error code: 1033", { status: 530 }), () => new Response("Bad gateway", { status: 502 }), () => { throw new TypeError("fetch failed"); }]) {
    const origin = fakeOrigin(reply);
    try {
      const shown = await worker.fetch(new Request("https://junction.example.test/", { headers: page }), env());
      assert.equal(shown.status, 503);
      const html = await shown.text();
      assert.ok(html.includes("offline") && html.includes('href="/__lock"'), html);
      const api = await worker.fetch(new Request("https://junction.example.test/api/info", { headers: { cookie } }), env());
      assert.ok(api.status >= 500, String(api.status));
      assert.ok(!(await api.text()).includes("<form"));
    } finally {
      origin.restore();
    }
  }
});

test("the origin's Access session never reaches the visitor, and a visitor's own Access credentials never reach the origin", async () => {
  const origin = fakeOrigin(() => {
    const reply = new Response("ok");
    reply.headers.append("set-cookie", "CF_Authorization=eyJ.jwt.sig; Path=/; Secure; HttpOnly");
    reply.headers.append("set-cookie", "theme=dark; Path=/");
    reply.headers.append("set-cookie", "CF_AppSession=abc; Path=/; Secure; HttpOnly");
    return reply;
  });
  try {
    const answer = await worker.fetch(
      new Request("https://junction.example.test/api/info", {
        headers: {
          cookie: `CF_Authorization=mine; ${await cookieFor()}; theme=dark; CF_AppSession=mine`,
          "cf-access-token": "mine",
          "cf-access-jwt-assertion": "mine",
        },
      }),
      env(),
    );
    assert.deepEqual(answer.headers.getSetCookie(), ["theme=dark; Path=/"]); // the app's own cookies pass
    const [sent] = origin.seen;
    assert.equal(sent.headers.get("cookie"), "theme=dark");
    assert.equal(sent.headers.get("cf-access-token"), null);
    assert.equal(sent.headers.get("cf-access-jwt-assertion"), null);
  } finally {
    origin.restore();
  }
});

test("the visitor's Host header is not copied to the origin request: its address decides the host", async () => {
  const origin = fakeOrigin();
  try {
    await worker.fetch(
      new Request("https://junction.example.test/api/info", {
        headers: { cookie: await cookieFor(), host: "junction.example.test" },
      }),
      env(),
    );
    assert.equal(origin.seen[0].headers.get("host"), null);
    assert.equal(origin.seen[0].url, `${ORIGIN}/api/info`);
  } finally {
    origin.restore();
  }
});

test("an upload is passed on as a stream: the origin is called before the body has been read to its end", async () => {
  let originCalled = false;
  let calledWhenBodyEnded = null;
  let pulls = 0;
  const body = new ReadableStream({
    pull(controller) {
      if (pulls++ === 0) return controller.enqueue(new TextEncoder().encode("part one, "));
      calledWhenBodyEnded = originCalled; // the last part is asked for only by whoever reads the body
      controller.enqueue(new TextEncoder().encode("part two"));
      controller.close();
    },
  });
  const original = globalThis.fetch;
  let received = "";
  globalThis.fetch = async (request) => {
    originCalled = true;
    received = await request.text();
    return new Response("stored", { status: 201 });
  };
  try {
    const answer = await worker.fetch(
      new Request("https://junction.example.test/api/projects", {
        method: "POST",
        headers: { cookie: await cookieFor(), "content-type": "application/zip" },
        body,
        duplex: "half",
      }),
      env(),
    );
    assert.equal(answer.status, 201);
    assert.equal(received, "part one, part two");
    assert.equal(calledWhenBodyEnded, true);
  } finally {
    globalThis.fetch = original;
  }
});

test("the code check compares the whole digest: a wrong code whose digest starts with the same byte is refused", async () => {
  const first = async (text) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)))[0];
  const want = await first(CODE);
  const twins = [];
  for (let n = 0; twins.length < 3; n++) if ((await first(`wrong-${n}`)) === want) twins.push(`wrong-${n}`);
  for (const twin of twins) assert.equal(await codeMatches(CODE, twin), false, twin);
});

test("the build: without the dataset it stops with a message and leaves the built assets as they are", async () => {
  const { spawnSync } = await import("node:child_process");
  const { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } = await import("node:fs");
  const site = new URL("../", import.meta.url);
  const marker = new URL("assets/.build-test-marker", site);
  mkdirSync(new URL("assets/", site), { recursive: true });
  writeFileSync(marker, "kept");
  try {
    const env = { ...process.env, STOA_DATASET: "" };
    const run = spawnSync("./build-assets.sh", { cwd: site, env, encoding: "utf8" });
    assert.notEqual(run.status, 0); // a start page that leads to a page that is not there is never built
    assert.match(run.stderr, /STOA_DATASET/);
    assert.equal(existsSync(marker) && readFileSync(marker, "utf8"), "kept");
  } finally {
    rmSync(marker, { force: true });
  }
});

test("the code form is a strip at the top of the demo page, in the page's flow, with the link to the credits", async () => {
  const answer = await worker.fetch(new Request("https://junction.example.test/"), env());
  const html = await answer.text();
  const form = html.indexOf('action="/__unlock"');
  assert.ok(form > html.indexOf("<body>") && form < html.indexOf("<h1>demo</h1>")); // above the page, not over it
  assert.ok(!html.includes("position:fixed")); // a fixed box covered the demo's own send button
  assert.ok(html.includes('href="/credits.html"'));
});
