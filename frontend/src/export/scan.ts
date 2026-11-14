import {
  getIssues,
  getModel,
  getProject,
  getProjectChecks,
  getProjectReview,
  getTakeoff,
} from '../api';
import type { Scan } from './csv';

/** Every answer the CSV needs (export.md "API calls"); any failure rejects, so no partial file is written. */
export async function loadScan(
  projectId: string,
  pack: string | null,
  signal: AbortSignal,
): Promise<Scan> {
  const opts = { signal };
  const [project, review, issues, checks] = await Promise.all([
    getProject(projectId, opts),
    getProjectReview(projectId, opts),
    getIssues(projectId, { ...opts, pack: pack ?? undefined }),
    pack ? getProjectChecks(projectId, { ...opts, pack }) : null,
  ]);
  const drawings = await Promise.all(
    review.drawings.map(async (d) => {
      const [takeoff, model] = await Promise.all([
        getTakeoff(d.drawing_id, { ...opts, project: projectId }),
        getModel(d.drawing_id, opts),
      ]);
      return { drawing_id: d.drawing_id, file: d.file, takeoff, model };
    }),
  );
  return { project, review, issues, checks, drawings };
}
