import type { Limits } from '../api';

const MB = 2 ** 20;

/** Why a file of `size` bytes is refused before upload, or null when it fits `limits.upload_mb`. */
export function uploadTooLarge(size: number, limits: Limits): string | null {
  if (size <= limits.upload_mb * MB) return null;
  return `This file is ${(size / MB).toFixed(1)} MB; the limit is ${String(limits.upload_mb)} MB.`;
}
