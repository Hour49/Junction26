import { describe, expect, it } from 'vitest';
import { never, mockApi, reply } from '../test/mockApi';
import {
  ApiError,
  askProject,
  askQuestion,
  getDrawing,
  getInfo,
  getProject,
  getProjectReview,
  getTakeoff,
  getTrace,
  getProjectTrace,
  getProjectQuestions,
  listProjects,
  pageUrl,
  evidenceUrl,
  getModel,
  postReview,
  postSignoff,
  previewUrl,
  startSample,
  takeoffCsvUrl,
  uploadProject,
} from '.';
import * as fx from './fixtures';
import type { Edit, SignOffRequest } from './types';

const pid = fx.project.id;
const did = fx.drawing.id;

describe('API client', () => {
  it('SH-23 each read function sends its method and path and resolves with the fixture', async () => {
    const api = mockApi({
      'GET /api/info': fx.info,
      'GET /api/projects': fx.projectList,
      [`GET /api/projects/${pid}`]: fx.project,
      [`GET /api/projects/${pid}/files/f1/trace`]: fx.trace,
      [`GET /api/projects/${pid}/trace`]: fx.projectTrace,
      [`GET /api/projects/${pid}/questions`]: fx.projectQuestions,
      [`GET /api/projects/${pid}/review`]: fx.projectReview,
      [`GET /api/drawings/${did}`]: fx.drawing,
      [`GET /api/drawings/${fx.takeoff.drawing_id}/takeoff`]: fx.takeoff,
    });
    expect(await getInfo()).toEqual(fx.info);
    expect(await listProjects()).toEqual(fx.projectList);
    expect(await getProject(pid)).toEqual(fx.project);
    expect(await getTrace(pid, 'f1')).toEqual(fx.trace);
    expect(await getProjectTrace(pid)).toEqual(fx.projectTrace);
    expect(await getProjectQuestions(pid)).toEqual(fx.projectQuestions);
    expect(await getProjectReview(pid)).toEqual(fx.projectReview);
    expect(await getDrawing(did)).toEqual(fx.drawing);
    expect(await getTakeoff(fx.takeoff.drawing_id)).toEqual(fx.takeoff);
    expect(api.calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET /api/info',
      'GET /api/projects',
      `GET /api/projects/${pid}`,
      `GET /api/projects/${pid}/files/f1/trace`,
      `GET /api/projects/${pid}/trace`,
      `GET /api/projects/${pid}/questions`,
      `GET /api/projects/${pid}/review`,
      `GET /api/drawings/${did}`,
      `GET /api/drawings/${fx.takeoff.drawing_id}/takeoff`,
    ]);
  });

  it('SH-24 uploadProject sends the raw file with ?name= and octet-stream', async () => {
    const api = mockApi({ 'POST /api/projects': fx.projectStarted });
    const file = new File([new Uint8Array([80, 75, 3, 4])], 'my plan #1.zip');
    expect(await uploadProject(file)).toEqual(fx.projectStarted);
    const [call] = api.calls;
    expect(call?.url).toBe('/api/projects?name=my%20plan%20%231.zip');
    expect(call?.body).toBe(file);
    const init = api.fetch.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/octet-stream');
  });

  it('SH-25 startSample sends fresh only when asked, and no body', async () => {
    const api = mockApi({ 'POST /api/projects/sample': fx.projectStarted });
    await startSample();
    await startSample({ fresh: true });
    expect(api.calls.map((c) => c.url)).toEqual([
      '/api/projects/sample',
      '/api/projects/sample?fresh=true',
    ]);
    expect(api.calls.every((c) => c.body === undefined || c.body === null)).toBe(true);
  });

  it('SH-26 askQuestion posts the JSON request and resolves answers and refusals', async () => {
    const api = mockApi({ 'POST /api/ask': fx.answer });
    expect(await askQuestion(fx.askRequest)).toEqual(fx.answer);
    expect(api.calls[0]?.body).toEqual(fx.askRequest);
    const init = api.fetch.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    mockApi({ 'POST /api/ask': fx.answerRefused });
    await expect(askQuestion(fx.askRequest)).resolves.toEqual(fx.answerRefused);
  });

  it('CH-9 askProject posts {question} to the project and resolves project_ask.json; a 409 rejects', async () => {
    const api = mockApi({ [`POST /api/projects/${pid}/ask`]: fx.projectAsk });
    expect(await askProject(pid, fx.projectAsk.question)).toEqual(fx.projectAsk);
    expect(api.calls[0]?.body).toEqual({ question: fx.projectAsk.question });
    const init = api.fetch.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    mockApi({ [`POST /api/projects/${pid}/ask`]: reply(409, fx.errorNotAllowed) });
    await expect(askProject(pid, 'q')).rejects.toMatchObject({ status: 409 });
  });

  it('SH-29 pageUrl builds the fixture page URL with the width', () => {
    const first = fx.drawing.pages[0];
    expect(pageUrl(did, 1)).toBe(`${first?.url ?? ''}?width=1600`);
    expect(pageUrl(did, 2, 3200)).toMatch(/\/pages\/2\.png\?width=3200$/);
    // @ts-expect-error 800 is not a page width the API serves
    pageUrl(did, 1, 800);
  });

  it('SH-31 a 404 rejects with the ApiError of error.json', async () => {
    mockApi({ [`GET /api/drawings/${did}`]: reply(404, fx.error) });
    const failed: unknown = await getDrawing(did).catch((e: unknown) => e);
    expect(failed).toBeInstanceOf(ApiError);
    const error = failed as ApiError;
    expect([error.status, error.code, error.detail]).toEqual([404, 'not-found', fx.error.detail]);
    expect(error.message).toBe(`${fx.error.detail} (not-found)`);
  });

  it('SH-33 a non-JSON error body gives http-<status>', async () => {
    mockApi({ 'GET /api/info': reply(502, '<html>Bad gateway</html>') });
    await expect(getInfo()).rejects.toMatchObject({
      status: 502,
      code: 'http-502',
      detail: 'the server answered 502',
    });
  });

  it('SH-34 a failed fetch is a network ApiError; an abort is an AbortError', async () => {
    const api = mockApi({ 'GET /api/info': never() });
    api.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(getInfo()).rejects.toMatchObject({ status: 0, code: 'network' });
    const abort = new AbortController();
    const pending = getInfo({ signal: abort.signal });
    abort.abort();
    const failed: unknown = await pending.catch((e: unknown) => e);
    expect(failed).not.toBeInstanceOf(ApiError);
    expect((failed as Error).name).toBe('AbortError');
  });

  const tid = fx.takeoff.drawing_id;
  const reviewPath = `POST /api/drawings/${tid}/review`;
  const signoffPath = `POST /api/drawings/${tid}/signoff`;

  it('SH-27 postReview and postSignoff send the request fixtures unchanged', async () => {
    const api = mockApi({ [reviewPath]: fx.takeoff, [signoffPath]: fx.takeoff });
    for (const edit of fx.reviewRequests) expect(await postReview(tid, edit)).toEqual(fx.takeoff);
    expect(await postSignoff(tid, fx.signoffRequest)).toEqual(fx.takeoff);
    expect(api.calls.map((c) => c.body)).toEqual([...fx.reviewRequests, fx.signoffRequest]);
  });

  it('SH-27 (#121) an unsettle edit and a settling sign-off are sent as given', async () => {
    const api = mockApi({ [reviewPath]: fx.takeoff, [signoffPath]: fx.takeoff });
    const unsettle: Edit = { action: 'unsettle', quantity: 'count:door' };
    const settle: SignOffRequest = { ...fx.signoffRequest, settle: true };
    await postReview(tid, unsettle);
    await postSignoff(tid, settle);
    expect(api.calls.map((c) => c.body)).toEqual([unsettle, settle]);
  });

  it('SH-28 zeros is sent only when passed', async () => {
    const api = mockApi({
      [`GET /api/drawings/${tid}/takeoff`]: fx.takeoff,
      [reviewPath]: fx.takeoff,
      [signoffPath]: fx.takeoff,
    });
    const edit = fx.reviewRequests[0];
    if (!edit) throw new Error('review_requests.json is empty');
    await getTakeoff(tid);
    await getTakeoff(tid, { zeros: true });
    await postReview(tid, edit);
    await postReview(tid, edit, { zeros: true });
    await postSignoff(tid, fx.signoffRequest);
    await postSignoff(tid, fx.signoffRequest, { zeros: true });
    expect(api.calls.map((c) => c.url.split('?')[1] ?? '')).toEqual([
      '',
      'zeros=true',
      '',
      'zeros=true',
      '',
      'zeros=true',
    ]);
    expect(takeoffCsvUrl(tid)).toBe(`/api/drawings/${tid}/takeoff.csv`);
    expect(takeoffCsvUrl(tid, { zeros: true })).toBe(`/api/drawings/${tid}/takeoff.csv?zeros=true`);
  });

  it('SH-30 previewUrl and evidenceUrl', () => {
    expect(previewUrl('5e0c1a2b3d4f', 'f2', 400)).toBe(
      '/api/projects/5e0c1a2b3d4f/files/f2/preview.png?width=400',
    );
    // encodeURIComponent: a space is %20 (the spec's `+` is the same query to the server)
    const doors =
      '/api/drawings/adeefbbcc17559fc/evidence.png?question=How%20many%20doors%20are%20there%3F';
    expect(evidenceUrl('adeefbbcc17559fc', 'How many doors are there?')).toBe(
      `${doors}&width=1600`,
    );
    expect(
      evidenceUrl('adeefbbcc17559fc', 'How many doors are there?', { project: '5e0c1a2b3d4f' }),
    ).toBe(`${doors}&width=1600&project=5e0c1a2b3d4f`);
    expect(evidenceUrl('adeefbbcc17559fc', 'How many doors are there?', { width: 400 })).toBe(
      `${doors}&width=400`,
    );
  });

  it('SH-32 a 422 keeps the validation errors', async () => {
    const errors = [{ loc: ['body', 'question'], msg: 'String should have at least 1 character' }];
    mockApi({
      'POST /api/ask': reply(422, { detail: 'question: too short', code: 'validation', errors }),
    });
    await expect(askQuestion({ ...fx.askRequest, question: '' })).rejects.toMatchObject({
      status: 422,
      code: 'validation',
      errors,
    });
  });

  it('SH-35 every function passes the caller signal to fetch', async () => {
    const edit = fx.reviewRequests[0];
    if (!edit) throw new Error('review_requests.json is empty');
    const api = mockApi({
      'GET /api/info': fx.info,
      'POST /api/projects': fx.projectStarted,
      'POST /api/projects/sample': fx.projectStarted,
      'GET /api/projects': fx.projectList,
      [`GET /api/projects/${pid}`]: fx.project,
      [`GET /api/projects/${pid}/files/f1/trace`]: fx.trace,
      [`GET /api/projects/${pid}/trace`]: fx.projectTrace,
      [`GET /api/projects/${pid}/questions`]: fx.projectQuestions,
      [`GET /api/projects/${pid}/review`]: fx.projectReview,
      [`GET /api/drawings/${did}`]: fx.drawing,
      [`GET /api/drawings/${did}/model`]: {},
      'POST /api/ask': fx.answer,
      [`GET /api/drawings/${tid}/takeoff`]: fx.takeoff,
      [reviewPath]: fx.takeoff,
      [signoffPath]: fx.takeoff,
    });
    const signal = new AbortController().signal;
    const opts = { signal };
    await Promise.all([
      getInfo(opts),
      uploadProject(new File(['x'], 'a.zip'), opts),
      startSample(opts),
      listProjects(opts),
      getProject(pid, opts),
      getTrace(pid, 'f1', opts),
      getProjectTrace(pid, opts),
      getProjectQuestions(pid, opts),
      getProjectReview(pid, opts),
      getDrawing(did, opts),
      getModel(did, opts),
      askQuestion(fx.askRequest, opts),
      getTakeoff(tid, opts),
      postReview(tid, edit, opts),
      postSignoff(tid, fx.signoffRequest, opts),
    ]);
    const signals = api.fetch.mock.calls.map(([, init]) => init?.signal);
    expect(signals).toHaveLength(15);
    expect(signals.every((s) => s === signal)).toBe(true);
  });

  it('R1-PS-1 (SH-44) getDrawing passes the project when given', async () => {
    const api = mockApi({ [`GET /api/drawings/${did}`]: fx.drawing });
    expect(await getDrawing(did, { project: pid })).toEqual(fx.drawing);
    expect(await getDrawing(did)).toEqual(fx.drawing);
    expect(api.calls.map((c) => c.url)).toEqual([
      `/api/drawings/${did}?project=${pid}`,
      `/api/drawings/${did}`,
    ]);
  });

  it('R1-PS-2 (SH-45) askQuestion sends project_id as given, and none when absent', async () => {
    const api = mockApi({ 'POST /api/ask': fx.answer });
    await askQuestion({ ...fx.askRequest, project_id: pid });
    await askQuestion(fx.askRequest);
    expect(api.calls.map((c) => c.body)).toEqual([
      { ...fx.askRequest, project_id: pid },
      fx.askRequest,
    ]);
    expect(api.calls[1]?.body).not.toHaveProperty('project_id');
  });

  it('R1-PS-3 (SH-46) the takeoff calls pass the project when given, after zeros', async () => {
    const api = mockApi({
      [`GET /api/drawings/${tid}/takeoff`]: fx.takeoff,
      [reviewPath]: fx.takeoff,
      [signoffPath]: fx.takeoff,
    });
    const edit = fx.reviewRequests[0];
    if (!edit) throw new Error('review_requests.json is empty');
    await getTakeoff(tid, { project: pid });
    await getTakeoff(tid, { zeros: true, project: pid });
    await postReview(tid, edit, { project: pid });
    await postSignoff(tid, fx.signoffRequest, { zeros: false, project: pid });
    await getTakeoff(tid);
    expect(api.calls.map((c) => c.url.split('?')[1] ?? '')).toEqual([
      `project=${pid}`,
      `zeros=true&project=${pid}`,
      `project=${pid}`,
      `zeros=false&project=${pid}`,
      '',
    ]);
    expect(takeoffCsvUrl(tid, { project: pid })).toBe(
      `/api/drawings/${tid}/takeoff.csv?project=${pid}`,
    );
    expect(takeoffCsvUrl(tid, { zeros: true, project: pid })).toBe(
      `/api/drawings/${tid}/takeoff.csv?zeros=true&project=${pid}`,
    );
  });
});
