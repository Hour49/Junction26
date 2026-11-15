// R4-B10: a sign-off names the value the surveyor saw, so the server refuses (409) one that changed since.
import type { SignOffRequest } from '../api';

/** The sign-off body's field for the value on screen. null until the server takes it: its request model refuses
 * unknown fields, so sending it earlier would refuse every sign-off. Setting the name is the whole change. */
export const SEEN_VALUE_FIELD: string | null = null;

/** The sign-off request for a row: undo, or a sign-off of the value on screen. */
export function signoffBody(
  row: { key: string; value: number },
  by: string,
  undo: boolean,
  field: string | null = SEEN_VALUE_FIELD,
): SignOffRequest {
  // undo defaults to false server-side; the sign-off body is signoff_request.json as is
  if (undo) return { quantity: row.key, by, undo: true };
  return { quantity: row.key, by, ...(field ? { [field]: row.value } : {}) } as SignOffRequest;
}
