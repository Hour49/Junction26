import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "../src/index.js";

const PAGE = "<html><body><h1>demo</h1></body></html>";

const env = () => ({
  ASSETS: {
    fetch: async (request) => {
      const { pathname } = new URL(request.url);
      if (pathname === "/" || pathname === "/credits.html") {
        return new Response(PAGE, { headers: { "content-type": "text/html", etag: '"page"' } });
      }
      if (pathname === "/style.css") return new Response("a{}", { headers: { "content-type": "text/css" } });
      return new Response("not found", { status: 404 });
    },
  },
});

const get = (path, init) => worker.fetch(new Request(`https://junction.example.test${path}`, init), env());

test("a page is the demo with the Credits strip on top, in the page's flow, and no access code form", async () => {
  for (const path of ["/", "/credits.html"]) {
    const answer = await get(path);
    assert.equal(answer.status, 200);
    const html = await answer.text();
    const strip = html.indexOf('href="/credits.html"');
    assert.ok(strip > html.indexOf("<body>") && strip < html.indexOf("<h1>demo</h1>"), path); // above the page
    assert.ok(!html.includes("position:fixed")); // a fixed box covered the demo's own send button
    assert.ok(!/<form|<input|access code|__unlock/i.test(html), path);
    assert.equal(answer.headers.get("etag"), null); // the asset's etag is for the page without the strip
  }
});

test("assets other than pages and missing files pass through untouched", async () => {
  const css = await get("/style.css");
  assert.equal(await css.text(), "a{}");
  assert.equal((await get("/nothing-here.png")).status, 404);
  const head = await get("/", { method: "HEAD" });
  assert.equal(head.status, 200);
});

test("the old access code links land on the demo, whatever the method", async () => {
  for (const [path, method] of [["/__unlock", "GET"], ["/__unlock", "POST"], ["/__lock", "GET"]]) {
    const init = method === "POST" ? { method, body: new URLSearchParams({ code: "x" }) } : { method };
    const answer = await get(path, init);
    assert.equal(answer.status, 303, `${method} ${path}`);
    assert.equal(answer.headers.get("location"), "/");
    assert.equal(answer.headers.get("set-cookie"), null);
  }
});

test("the app's API answers that the app is offline, as JSON", async () => {
  for (const path of ["/api/info", "/api/projects/p1/ask"]) {
    const answer = await get(path);
    assert.equal(answer.status, 410, path);
    assert.match(answer.headers.get("content-type"), /application\/json/);
    assert.match((await answer.json()).error, /offline/);
  }
});

test("only GET and HEAD are served, and nothing is fetched from anywhere but the assets", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response("from somewhere else");
  };
  try {
    for (const method of ["POST", "PUT", "DELETE", "PATCH"]) {
      for (const path of ["/", "/api/projects"]) {
        const answer = await get(path, { method, body: "x" });
        assert.equal(answer.status, 405, `${method} ${path}`);
        assert.equal(answer.headers.get("allow"), "GET, HEAD");
      }
    }
    await get("/");
    await get("/api/info");
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = original;
  }
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
