// Pure helpers of the 3D view (docs/specs/frontend/model-3d.md).
import { ApiError, errorText, type FileStatus, type Model3d } from '../api';

/** The file's 3D model, null when it has none (not IFC, set aside, or MODEL_3D off). */
export const model3dOf = (file: FileStatus): Model3d | null => file.model_3d ?? null;

export const UNAVAILABLE = 'the model cannot be shown in 3D';

/** Why the view could not open, and whether trying again can help. */
export function failure(error: unknown): { reason: string; retry: boolean } {
  if (error instanceof ApiError && error.status === 422)
    return { reason: error.detail, retry: false };
  if (error instanceof ApiError && error.status === 404)
    return { reason: 'no 3D model for this file', retry: false };
  if (error instanceof ApiError) return { reason: error.message, retry: true };
  return { reason: errorText(error).detail, retry: true };
}
