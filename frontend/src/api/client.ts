// One function per endpoint of docs/API.md (v1); relative URLs, the dev/preview server proxies /api.
import { ApiError, errorOf } from './errors';
import type {
  AnswerView,
  AskRequest,
  DrawingView,
  Edit,
  FileStatus,
  FileTrace,
  ProjectTrace,
  ProjectQuestions,
  Info,
  ProjectAnswer,
  ProjectList,
  ProjectReview,
  ProjectView,
  RelevanceRequest,
  TriageRequest,
  SignOffRequest,
  Started,
  Takeoff,
  DrawingChecks,
  IssueList,
  ProjectChecks,
} from './types';

export type PageWidth = 400 | 1600 | 3200;

export interface Opts {
  signal?: AbortSignal;
}
export interface ZerosOpts extends Opts {
  zeros?: boolean;
  /** The project the screen shows the drawing in (backend PR #74): the takeoff's names are its names. */
  project?: string;
}

type Query = Record<string, string | number | boolean | undefined>;

const seg = encodeURIComponent;

function withQuery(path: string, query: Query): string {
  const parts = Object.entries(query)
    .filter((entry): entry is [string, string | number | boolean] => entry[1] !== undefined)
    .map(([key, value]) => `${seg(key)}=${seg(String(value))}`);
  return parts.length ? `${path}?${parts.join('&')}` : path;
}

function isAbort(error: unknown): boolean {
  return (error as { name?: unknown } | null)?.name === 'AbortError';
}

async function call<T>(
  method: 'GET' | 'POST',
  url: string,
  opts: Opts & { body?: BodyInit; type?: string } = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      body: opts.body ?? null,
      headers: opts.type ? { 'Content-Type': opts.type } : undefined,
      signal: opts.signal ?? null,
    });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(0, 'network', 'cannot reach the server');
  }
  if (!response.ok) throw await errorOf(response);
  return (await response.json()) as T;
}

function postJson<T>(url: string, body: unknown, opts: Opts = {}): Promise<T> {
  return call<T>('POST', url, { ...opts, body: JSON.stringify(body), type: 'application/json' });
}

export const getInfo = (opts?: Opts) => call<Info>('GET', '/api/info', opts);

export const uploadProject = (file: File, opts?: Opts) =>
  call<Started>('POST', withQuery('/api/projects', { name: file.name }), {
    ...opts,
    body: file,
    type: 'application/octet-stream',
  });

export const startSample = (opts: Opts & { fresh?: boolean } = {}) =>
  call<Started>('POST', withQuery('/api/projects/sample', { fresh: opts.fresh }), opts);

export const listProjects = (opts?: Opts) => call<ProjectList>('GET', '/api/projects', opts);

export const getProject = (projectId: string, opts?: Opts) =>
  call<ProjectView>('GET', `/api/projects/${seg(projectId)}`, opts);

export const getTrace = (projectId: string, fileId: string, opts?: Opts) =>
  call<FileTrace>('GET', `/api/projects/${seg(projectId)}/files/${seg(fileId)}/trace`, opts);

/** Every file's trace in one request, files in upload order (#120). */
export const getProjectTrace = (projectId: string, opts?: Opts) =>
  call<ProjectTrace>('GET', `/api/projects/${seg(projectId)}/trace`, opts);

/** The questions asked about the project, newest first (#121; only asks that sent `project_id` are logged). */
export const getProjectQuestions = (projectId: string, opts?: Opts) =>
  call<ProjectQuestions>('GET', `/api/projects/${seg(projectId)}/questions`, opts);

export const getProjectReview = (projectId: string, opts?: Opts) =>
  call<ProjectReview>('GET', `/api/projects/${seg(projectId)}/review`, opts);

/** `project`: the project the screen shows the drawing in, so `file` and `reader.source` are its names. */
export const getDrawing = (drawingId: string, opts: Opts & { project?: string } = {}) =>
  call<DrawingView>(
    'GET',
    withQuery(`/api/drawings/${seg(drawingId)}`, { project: opts.project }),
    opts,
  );

/** extraction_v1, not typed in the OpenAPI document. */
export const getModel = (drawingId: string, opts?: Opts) =>
  call<Record<string, unknown>>('GET', `/api/drawings/${seg(drawingId)}/model`, opts);

export const askQuestion = (body: AskRequest, opts?: Opts) =>
  postJson<AnswerView>('/api/ask', body, opts);

/** One question on every drawing of the project (#135): the parts, and a total only where one means something. */
export const askProject = (projectId: string, question: string, opts?: Opts) =>
  postJson<ProjectAnswer>(`/api/projects/${seg(projectId)}/ask`, { question }, opts);

export const getTakeoff = (drawingId: string, opts: ZerosOpts = {}) =>
  call<Takeoff>(
    'GET',
    withQuery(`/api/drawings/${seg(drawingId)}/takeoff`, {
      zeros: opts.zeros,
      project: opts.project,
    }),
    opts,
  );

export const postReview = (drawingId: string, edit: Edit, opts: ZerosOpts = {}) =>
  postJson<Takeoff>(
    withQuery(`/api/drawings/${seg(drawingId)}/review`, {
      zeros: opts.zeros,
      project: opts.project,
    }),
    edit,
    opts,
  );

export const postSignoff = (drawingId: string, body: SignOffRequest, opts: ZerosOpts = {}) =>
  postJson<Takeoff>(
    withQuery(`/api/drawings/${seg(drawingId)}/signoff`, {
      zeros: opts.zeros,
      project: opts.project,
    }),
    body,
    opts,
  );

/** A person's call on a triaged file (decision 0010, file-triage.md); answers the file as it now stands. */
export const postRelevance = (
  projectId: string,
  fileId: string,
  body: RelevanceRequest,
  opts?: Opts,
) =>
  postJson<FileStatus>(
    `/api/projects/${seg(projectId)}/files/${seg(fileId)}/relevance`,
    body,
    opts,
  );

/** "Read it as a plan" (0010, #152): queues the file for a plan read; answers 202 with the file, queued. */
export const readAsPlan = (projectId: string, fileId: string, by: string, opts?: Opts) =>
  postJson<FileStatus>(
    `/api/projects/${seg(projectId)}/files/${seg(fileId)}/triage`,
    { class: 'floor_plan', by } satisfies TriageRequest,
    opts,
  );

export const pageUrl = (drawingId: string, page: number, width: PageWidth = 1600) =>
  withQuery(`/api/drawings/${seg(drawingId)}/pages/${String(page)}.png`, { width });

export const previewUrl = (projectId: string, fileId: string, width: PageWidth = 1600) =>
  withQuery(`/api/projects/${seg(projectId)}/files/${seg(fileId)}/preview.png`, { width });

export const takeoffCsvUrl = (
  drawingId: string,
  opts: { zeros?: boolean; project?: string } = {},
) =>
  withQuery(`/api/drawings/${seg(drawingId)}/takeoff.csv`, {
    zeros: opts.zeros,
    project: opts.project,
  });

/** `project`: the project the screen shows the answer in, so the picture carries its review edits and
 * sign-offs (backend #90). */
export const evidenceUrl = (
  drawingId: string,
  question: string,
  opts: { width?: PageWidth; project?: string } = {},
) =>
  withQuery(`/api/drawings/${seg(drawingId)}/evidence.png`, {
    question,
    width: opts.width ?? 1600,
    project: opts.project,
  });

// #139 / #140 (board #142; shared.md "Checks and issues"). `pack` is required for checks: the server 404s without it.

export const getDrawingChecks = (
  drawingId: string,
  opts: Opts & { pack: string; project?: string },
) =>
  call<DrawingChecks>(
    'GET',
    withQuery(`/api/drawings/${seg(drawingId)}/checks`, { pack: opts.pack, project: opts.project }),
    opts,
  );

export const getProjectChecks = (projectId: string, opts: Opts & { pack: string }) =>
  call<ProjectChecks>(
    'GET',
    withQuery(`/api/projects/${seg(projectId)}/checks`, { pack: opts.pack }),
    opts,
  );

export const getIssues = (projectId: string, opts: Opts & { pack?: string } = {}) =>
  call<IssueList>(
    'GET',
    withQuery(`/api/projects/${seg(projectId)}/issues`, { pack: opts.pack }),
    opts,
  );

/** The issues as CSV (same rows as `getIssues`). */
export const issuesCsvUrl = (projectId: string, pack?: string) =>
  withQuery(`/api/projects/${seg(projectId)}/issues.csv`, { pack });

/** The export bundle: issues.csv (with an `n` column) plus one PNG per drawing page with the issues drawn and numbered. */
export const issuesZipUrl = (projectId: string, pack?: string) =>
  withQuery(`/api/projects/${seg(projectId)}/issues.zip`, { pack });
