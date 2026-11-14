// The access gate's pure parts: the signed cookie, the code check, cookie headers. Web APIs only
// (crypto.subtle, TextEncoder), so the same code runs in the Worker and under `node --test`.

const encoder = new TextEncoder();

export const COOKIE = "h49_gate";
export const TTL_S = 24 * 60 * 60;
const VERSION = "v1";

function b64url(bytes) {
  let text = "";
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function unb64url(text) {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4);
  const raw = atob(padded);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

function hmacKey(secret, usage) {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, [usage]);
}

/** The cookie value that opens the app until `expires` (epoch seconds). */
export async function sign(secret, expires) {
  const payload = `${VERSION}.${expires}`;
  const mac = await crypto.subtle.sign("HMAC", await hmacKey(secret, "sign"), encoder.encode(payload));
  return `${payload}.${b64url(new Uint8Array(mac))}`;
}

/** Whether `value` is a cookie `sign` made with `secret` that has not expired at `now` (epoch seconds). */
export async function verify(secret, value, now) {
  if (!secret || typeof value !== "string") return false;
  const parts = value.split(".");
  if (parts.length !== 3 || parts[0] !== VERSION || !/^\d{1,12}$/.test(parts[1])) return false;
  if (!(Number(parts[1]) > now)) return false;
  try {
    // crypto.subtle.verify compares the MAC in constant time
    return await crypto.subtle.verify(
      "HMAC",
      await hmacKey(secret, "verify"),
      unb64url(parts[2]),
      encoder.encode(`${parts[0]}.${parts[1]}`),
    );
  } catch {
    return false;
  }
}

async function digest(text) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(text)));
}

/** Whether `given` is the access code, compared as SHA-256 digests in constant time. */
export async function codeMatches(expected, given) {
  if (!expected || typeof given !== "string" || given === "") return false;
  const [a, b] = await Promise.all([digest(expected), digest(given.trim())]);
  let different = 0;
  for (let at = 0; at < a.length; at++) different |= a[at] ^ b[at];
  return different === 0;
}

/** One cookie's value from a Cookie header, or null. */
export function cookieValue(header, name) {
  for (const part of (header || "").split(";")) {
    const at = part.indexOf("=");
    if (at > 0 && part.slice(0, at).trim() === name) return part.slice(at + 1).trim();
  }
  return null;
}

/** The Cookie header without cookie `name` (a name, or a test of names), or null when nothing else is left. */
export function withoutCookie(header, name) {
  const dropped = typeof name === "function" ? name : (given) => given === name;
  const kept = (header || "")
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part && !dropped(part.slice(0, Math.max(part.indexOf("="), 0)).trim()));
  return kept.length ? kept.join("; ") : null;
}

export function setCookie(value, maxAge) {
  return `${COOKIE}=${value}; Max-Age=${maxAge}; Path=/; HttpOnly; Secure; SameSite=Lax`;
}
