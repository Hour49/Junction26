// A thread kept in this tab's sessionStorage (the engineer page R3-L2, the agent chat answers-5). It is read back
// only when it carries KEPT_VERSION; the page also checks each turn has what it reads. Anything else is removed, so
// a value an older build wrote never takes the page down (QA R4-C13). Bump KEPT_VERSION when a kept turn's shape
// changes.
export const KEPT_VERSION = 1;

export const hasKeys = (
  value: unknown,
  keys: readonly string[],
): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && keys.every((k) => k in value);

export function dropKept(key: string) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // no storage (private mode): nothing kept
  }
}

/** The kept value's fields; null when nothing is kept, or when it is another version or not JSON (then removed). */
export function readKept(key: string): Record<string, unknown> | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return null;
    const value: unknown = JSON.parse(raw);
    if (hasKeys(value, ['v']) && value.v === KEPT_VERSION) return value;
  } catch {
    // not JSON, or no storage
  }
  dropKept(key);
  return null;
}

export function writeKept(key: string, fields: Record<string, unknown>) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ v: KEPT_VERSION, ...fields }));
  } catch {
    // full or blocked storage: the thread just isn't kept
  }
}
