import type { Limits } from '../api';

const MB = 2 ** 20;

/** Why a file of `size` bytes is refused before upload, or null when it fits `limits.upload_mb`. */
export function uploadTooLarge(size: number, limits: Limits): string | null {
  if (size <= limits.upload_mb * MB) return null;
  return `This file is ${(size / MB).toFixed(1)} MB; the limit is ${String(limits.upload_mb)} MB.`;
}

/** The API's `name` query is at most 255 characters (backend/app/api/projects.py), counted in code points. */
const NAME_MAX = 255;

/** Why a file named `name` is refused before upload, or null when the API takes the name. */
export function nameTooLong(name: string): string | null {
  const n = Array.from(name).length;
  if (n <= NAME_MAX) return null;
  return `This file name is ${String(n)} characters long; the limit is ${String(NAME_MAX)}. Rename the file and try again.`;
}
