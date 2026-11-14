# site/: junction.hour49.com, the access gate

A Cloudflare Worker (`src/index.js`, `src/gate.js`) in front of the real app. Bogdan's design (2026-11-14): anyone
with the shared access code gets the app, everyone else gets the HTML demo.

- No valid cookie: the HTML demo from `assets/` (built by `build-assets.sh`: `demo/vellum` at `/`, the older mock at
  `/mock`) and a small "Have an access code?" form. `/api/*` answers 401.
- `POST /__unlock` with the right code (secret `ACCESS_CODE`, compared as SHA-256 digests in constant time) sets
  `h49_gate`: an HMAC-signed value with a 24 h expiry (key: secret `COOKIE_KEY`), HttpOnly, Secure, SameSite=Lax, and
  redirects to `/`. `/__lock` clears it.
- With a valid cookie every request is proxied, streamed, to the tunnel origin (secret `ORIGIN_URL`), with the
  Cloudflare Access service-token headers added (`ACCESS_CLIENT_ID`, `ACCESS_CLIENT_SECRET`). The origin sits behind
  an Access app that only accepts that token, so the app is reachable only through this Worker. The gate cookie is
  removed from the request before it is forwarded.
- With `ACCESS_CODE` or `COOKIE_KEY` unset nothing unlocks.
- Pages (HTML) are sent with `Cache-Control: no-store` on both sides, because `/` is the demo without the cookie and
  the app with it.
- When the origin does not answer (502, 503, 530 or no reply), a page request gets "The app is offline right now" with
  a link back to the demo (`/__lock`); API calls get the error as it is.
- Cloudflare Access's own cookies and headers for the origin (`CF_Authorization` and the other `CF_` cookies,
  `cf-access-token`, `cf-access-jwt-assertion`) pass in neither direction, and the visitor's `Host` header is not
  copied: the origin's address decides the host.

Closing it again:

- A new `COOKIE_KEY` ends every open session at once. A new `ACCESS_CODE` only stops new unlocks: cookies already
  given stay valid until they expire (24 h) or the key changes.
- Back to an earlier version of the Worker: `npx wrangler@4.161.0 versions list`, then
  `npx wrangler@4.161.0 versions deploy <version id>@100% -y` (or `npx wrangler@4.161.0 rollback <version id>`).
- Stopping the tunnel closes the app and leaves the demo up.

Tests: `cd site && npm test` (Node's test runner, no dependencies). To run it locally against the real app:
`npx wrangler@4.161.0 dev --env preview --var ACCESS_CODE:... --var COOKIE_KEY:... --var ORIGIN_URL:http://127.0.0.1:8871
--var ACCESS_CLIENT_ID:... --var ACCESS_CLIENT_SECRET:...`.

Build and deploy: `./build-assets.sh`, then `npx wrangler@4.161.0 deploy --secrets-file <file>` (the five secrets as
JSON in a file outside the repo, readable only by you, deleted after; never in this folder); the steps are in
`.agents/deploy/RUNBOOK.md` (local, gitignored). `build-assets.sh` refuses
partner data: the Stoa scans (`demo/vellum/stoa/archive`) stop it, and the one Swiss Dwellings floor in
`demo/vellum/stoa` goes in only with `INCLUDE_STOA_FLOOR=1`, because its answer key comes from Stoa's questions file.

`public/` is the earlier static placeholder page, kept for reference; the Worker does not serve it.
