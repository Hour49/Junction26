// R4-B10: a sign-off names the value the surveyor saw, so the server refuses (409) one that changed since.
import type { SignOffRequest } from '../api';

/** The sign-off body's field for the value on screen (#634); with it goes `expected_unit`, the row's unit. */
export const SEEN_VALUE_FIELD: string | null = 'expected_value';

/** The sign-off request for a row: undo, or a sign-off of the value on screen. */
export function signoffBody(
  row: { key: string; value: number; unit?: string },
  by: string,
  undo: boolean,
  field: string | null = SEEN_VALUE_FIELD,
): SignOffRequest {
  // undo defaults to false server-side; the sign-off body is signoff_request.json as is
  if (undo) return { quantity: row.key, by, undo: true };
  const seen = field
    ? { [field]: row.value, ...(row.unit ? { expected_unit: row.unit } : {}) }
    : {};
  return { quantity: row.key, by, ...seen } as SignOffRequest;
}
