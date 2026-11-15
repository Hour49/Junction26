// One function per endpoint of docs/API.md (v1); relative URLs, the dev/preview server proxies /api.
import { ApiError, errorOf, OFFLINE } from './errors';
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
  SampleList,
  Started,
  Takeoff,
  DrawingChecks,
  Issue,
  IssueAnswerRequest,
  IssueList,
  ProjectChecks,
} from './types';
import type { ChatRequest, ChatTurn, Proposal } from '../agent/agent';

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

/** The slowest GET seen is ~11 s (issues of a 40-file project); Cloudflare gives up on the backend at 100 s. */
export const GET_TIMEOUT_MS = 60_000;

type CallOpts = Opts & { body?: BodyInit; type?: string; bytes?: boolean };

/** A JSON GET with no answer in GET_TIMEOUT_MS (a frozen backend) is aborted and rejects as `timeout`, so the
 * screen shows its error view with Retry instead of loading forever. POSTs (asks can take minutes) and byte
 * downloads are not timed. */
async function call<T>(method: 'GET' | 'POST', url: string, opts: CallOpts = {}): Promise<T> {
  if (method !== 'GET' || opts.bytes) return send<T>(method, url, opts);
  const clock = new AbortController();
  const stop = () => {
    clock.abort();
  };
  opts.signal?.addEventListener('abort', stop);
  if (opts.signal?.aborted) stop();
  const timer = setTimeout(stop, GET_TIMEOUT_MS);
  try {
    return await send<T>(method, url, { ...opts, signal: clock.signal });
  } catch (error) {
    if (clock.signal.aborted && !opts.signal?.aborted) throw new ApiError(0, 'timeout', OFFLINE);
    throw error;
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', stop);
  }
}

async function send<T>(method: 'GET' | 'POST', url: string, opts: CallOpts): Promise<T> {
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
  return (opts.bytes ? await response.arrayBuffer() : await response.json()) as T;
}

function postJson<T>(url: string, body: unknown, opts: Opts = {}): Promise<T> {
  return call<T>('POST', url, { ...opts, body: JSON.stringify(body), type: 'application/json' });
}

export const getInfo = (opts?: Opts) => call<Info>('GET', '/api/info', opts);

/** POST /api/projects with the file as body, over XHR because fetch reports no upload progress: `onProgress`
 * gets the bytes sent so far and the total as they go out. Errors as `call`'s: an HTTP error is its ApiError, no
 * answer at all is a network ApiError, an abort rejects with an AbortError. */
export function uploadProject(
  file: File,
  opts: Opts & { onProgress?: (sent: number, total: number) => void } = {},
): Promise<Started> {
  return new Promise<Started>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', withQuery('/api/projects', { name: file.name }));
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(e.loaded, e.total);
    };
    xhr.onload = () => {
      const response = new Response(xhr.responseText, { status: xhr.status });
      if (response.ok)
        void response.json().then((body) => {
          resolve(body as Started);
        }, reject);
      else void errorOf(response).then(reject);
    };
    xhr.onerror = () => {
      reject(new ApiError(0, 'network', 'the connection was lost while sending the file'));
    };
    xhr.onabort = () => {
      reject(new DOMException('aborted', 'AbortError'));
    };
    opts.signal?.addEventListener('abort', () => {
      xhr.abort();
    });
    xhr.send(file);
  });
}

/** `id`: one of listSamples (none: the synthetic sample). */
export const startSample = (opts: Opts & { fresh?: boolean; id?: string } = {}) =>
  call<Started>(
    'POST',
    withQuery('/api/projects/sample', { id: opts.id, fresh: opts.fresh }),
    opts,
  );

/** The sample projects the home screen offers; the synthetic one ("sample") is always there. */
export const listSamples = (opts?: Opts) => call<SampleList>('GET', '/api/projects/samples', opts);

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

/** The file's building model as one GLB (model-3d.md): 409 `converting`, 422 `too_big` / `no_geometry`. */
export const getModelGlb = (projectId: string, fileId: string, opts?: Opts) =>
  call<ArrayBuffer>('GET', `/api/projects/${seg(projectId)}/files/${seg(fileId)}/model.glb`, {
    ...opts,
    bytes: true,
  });

/** extraction_v1, not typed in the OpenAPI document. */
export const getModel = (drawingId: string, opts?: Opts) =>
  call<Record<string, unknown>>('GET', `/api/drawings/${seg(drawingId)}/model`, opts);

export const askQuestion = (body: AskRequest, opts?: Opts) =>
  postJson<AnswerView>('/api/ask', body, opts);

/** One question on every drawing of the project (#135): the parts, and a total only where one means something. */
export const askProject = (projectId: string, question: string, opts?: Opts) =>
  postJson<ProjectAnswer>(`/api/projects/${seg(projectId)}/ask`, { question }, opts);

/** One agent chat turn (decision 0013, AC-34): the first turn omits `chat_id`, later turns send the one returned. */
export const chatTurn = (projectId: string, body: ChatRequest, opts?: Opts) =>
  postJson<ChatTurn>(`/api/projects/${seg(projectId)}/chat`, body, opts);

/** Accept or reject an edit proposal; resolves the proposal with its new `state` (409 when already decided). */
export const decideProposal = (
  projectId: string,
  chatId: string,
  proposalId: string,
  action: 'accept' | 'reject',
  opts?: Opts,
) =>
  postJson<Proposal>(
    `/api/projects/${seg(projectId)}/chat/${seg(chatId)}/proposals/${seg(proposalId)}`,
    { action },
    opts,
  );

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

/** A photo added to a done project from the chat (#203, chat.md CH-18): 202 with the new file, queued. */
export const addProjectFile = (projectId: string, file: File, opts?: Opts) =>
  call<FileStatus>(
    'POST',
    withQuery(`/api/projects/${seg(projectId)}/files`, { name: file.name }),
    { ...opts, body: file, type: 'application/octet-stream' },
  );

/** A person's answer to an issue, or `{undo: true}` (#223); answers the issue as it now stands. Answering does
 * not close it. A code check's issue needs its `pack` (404 without). */
export const answerIssue = (
  projectId: string,
  issueId: string,
  body: IssueAnswerRequest,
  opts: Opts & { pack?: string } = {},
) =>
  postJson<Issue>(
    withQuery(`/api/projects/${seg(projectId)}/issues/${seg(issueId)}/answer`, { pack: opts.pack }),
    body,
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
