// Trace view v5 (advanced-ingest.md AD-110, AD-100, AD-106, AD-115, AD-116): the finished sample's files by stage on
// Advanced, then one file's decisions and stages, at the project's viewport, on a no-keys backend.
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { type Page, type TestInfo } from '@playwright/test';
import { noKeys, sampleDone, shot as shotNow, watchErrors } from './support';

/** The bars grow in once (500 ms): screenshots wait for them to settle, so the picture shows the real widths. */
async function shot(page: Page, testInfo: TestInfo, name: string, offline: boolean) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished),
    ),
  );
  await shotNow(page, testInfo, name, offline);
}

test('AD-110 AD-100 AD-106 AD-115: files by stage, then one file on its time axis', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  const full = async (name: string) =>
    page.screenshot({
      path: path.join(
        testInfo.config.rootDir,
        '..',
        'screenshots',
        testInfo.project.name,
        `${name}.png`,
      ),
      fullPage: true,
    });

  await page.goto(`/#/p/${pid}?view=advanced`);
  const matrix = page.getByRole('region', { name: 'Files by stage' });
  const rows = matrix.getByRole('list', { name: 'Files' }).locator(':scope > li');
  await expect(rows).toHaveCount(12);
  // every finished file has its bar, which says its stages in words
  await expect(matrix.getByRole('img', { name: /^Unpack / }).first()).toBeVisible();
  await shot(page, testInfo, 'detail-advanced', offline);
  await full('detail-advanced-full');
  // AD-125: a path in the panel's running text (live line, log, Questions ready) keeps its file name on one line
  const names = page.locator('.adv-panel .adv-name');
  await expect(names.first()).toBeVisible();
  // lines a name's text takes: distinct tops of its text's boxes (the name is one inline-block box)
  const lines = await names.evaluateAll((els) =>
    els.map((e) => {
      const range = document.createRange();
      range.selectNodeContents(e);
      const tops = new Set([...range.getClientRects()].map((r) => Math.round(r.top)));
      return [e.textContent, tops.size];
    }),
  );
  expect(lines.filter(([, n]) => n !== 1)).toEqual([]);

  await matrix.getByRole('link', { name: 'plans/flat-b.pdf' }).click();
  await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/f\/f\d+$/);
  const decisions = page.getByRole('region', { name: 'Decisions' });
  await expect(decisions.getByText('1 conflict between the counts')).toBeVisible();
  await expect(decisions.getByText(/on the drawing, .* the second way/).first()).toBeVisible();
  await expect(decisions.getByText('Flagged for a look')).toBeVisible();
  const stages = page.getByRole('region', { name: 'Stages' });
  await expect(
    stages.getByRole('heading', { name: /^How it was read: \d+ stages$/ }),
  ).toBeVisible();
  await expect(stages.locator('.tl-span').first()).toBeVisible();
  await decisions.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'detail-trace', offline);
  await full('detail-trace-full');
  expect(errors).toEqual([]);
});

test('AD-116 nothing on the two views animates under reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const pid = await sampleDone(page);
  await page.goto(`/#/p/${pid}?view=advanced`);
  const bar = page.getByRole('region', { name: 'Files by stage' }).locator('.fm-segs').first();
  await expect(bar).toBeVisible();
  expect(await bar.evaluate((e) => getComputedStyle(e).animationName)).toBe('none');
  await page.getByRole('region', { name: 'Files by stage' }).getByRole('link').first().click();
  const span = page.getByRole('region', { name: 'Stages' }).locator('.tl-span').first();
  await expect(span).toBeVisible();
  expect(await span.evaluate((e) => getComputedStyle(e).animationName)).toBe('none');
});

// shortcut: the backend's fixtures and the no-keys run send `steps: []` (trace worker, 2026-11-15); until real step
// data lands, the browser check adds contract-shaped steps to the real trace response.
const STEPS = [
  {
    id: 'detector',
    label: 'Symbol detector, 8 views',
    did: '',
    at_ms: 0,
    ms: 1200,
    cost_usd: 0,
    state: 'done',
    found: { door: 31, window: 12 },
  },
  {
    id: 'rooms',
    label: 'Room reader (Gemini)',
    did: '9 rooms with names',
    at_ms: 0,
    ms: 4000,
    cost_usd: 0.012,
    state: 'done',
  },
  {
    id: 'carbon',
    label: 'Carbon counter',
    did: '',
    at_ms: 0,
    ms: 0,
    cost_usd: 0,
    state: 'skipped',
  },
  {
    id: 'printed_scale',
    label: 'Printed scale',
    did: 'no scale text found',
    at_ms: 1200,
    ms: 300,
    cost_usd: 0,
    state: 'failed',
  },
];

test('AD-103: the readers inside a stage, side by side on its time axis', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await page.route('**/api/projects/*/files/*/trace', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as {
      stages: { stage: string; ms: number; steps: unknown[] }[];
    };
    for (const s of body.stages)
      if (s.stage === 'extract') Object.assign(s, { ms: 4000, steps: STEPS });
    await route.fulfill({ response, json: body });
  });
  await page.goto(`/#/p/${pid}?view=advanced`);
  await page
    .getByRole('region', { name: 'Files by stage' })
    .getByRole('link', { name: 'plans/flat-a.pdf' })
    .click();
  const steps = page.getByRole('list', { name: 'Steps of Extract' });
  await expect(steps.getByRole('listitem')).toHaveCount(4);
  await expect(page.getByText('4 steps inside Extract, up to 2 side by side')).toBeVisible();
  await expect(steps.getByRole('img', { name: 'failed' })).toHaveCount(1);
  await expect(steps.getByRole('img', { name: 'skipped' })).toHaveCount(1);
  await steps.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'detail-steps', offline);
  expect(errors).toEqual([]);
});

// QA R4-A9 (advanced-ingest.md AD-127): the no-keys sample has no sheet-kind step, so the browser check marks one
// drawing `not_a_drawing` in the real project response, and gives its file the triage the backend derives it from.
const NOT_A_DRAWING = 'plans/flat-b.pdf';
const SHEET_DOUBT = {
  class: 'floor_plan',
  p_plan: 0.4,
  method: 'sheet kind',
  register: null,
  description: null,
  relevance: null,
  overruled: null,
  read_as_plan: null,
  verdict: null,
  note: null,
  sheet: {
    advanced: false,
    advanced_why: null,
    confidence: 0.4,
    decision: 'doubt',
    kind: 'not_a_drawing',
    kind_words: 'not a drawing',
    model: 'gemini-4-carbon',
    printed_scale: null,
    seen: 'a screenshot of a web page',
    sheet_number: null,
    takeoff_possible: false,
    title: null,
  },
};

test('AD-127 (QA R4-A9): a drawing called not a drawing is tagged on Advanced and on its file page', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  await page.route(
    (url) => url.pathname === `/api/projects/${pid}`,
    async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as { drawings: { file: string }[] };
      for (const d of body.drawings)
        if (d.file === NOT_A_DRAWING) Object.assign(d, { not_a_drawing: true });
      await route.fulfill({ response, json: body });
    },
  );
  await page.route('**/api/projects/*/files/*/trace', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { file: { path: string } };
    if (body.file.path === NOT_A_DRAWING) Object.assign(body.file, { triage: SHEET_DOUBT });
    await route.fulfill({ response, json: body });
  });

  // Takeoff (the done project's panel): the raw total with its note, the row tagged and not ready
  await page.goto(`/#/p/${pid}?view=advanced`);
  const drawings = page.locator('.adv-stats > div', { hasText: 'Drawings' }).first();
  await expect(drawings.locator('.adv-stat-note')).toHaveText('1 not a drawing');
  const row = page.locator('.adv-ready > ul > li', { hasText: `${NOT_A_DRAWING}:` });
  await expect(row.locator('.adv-tag')).toHaveText('not a drawing');
  await expect(row.locator('.adv-dot')).not.toHaveClass(/\bon\b/);
  await row.evaluate((e) => {
    e.scrollIntoView({ block: 'center' });
  });
  await shot(page, testInfo, 'detail-not-a-drawing-takeoff', offline);

  // Extract: picked in the drawing picker, the drawing carries the tag
  await page
    .getByRole('navigation', { name: 'Steps' })
    .getByRole('button', { name: /^Extract/ })
    .click();
  const picker = page.locator('.adv-pick select');
  await picker.selectOption({ label: `${NOT_A_DRAWING} · not a drawing` });
  await expect(page.locator('.adv-visual .adv-tag')).toHaveText('not a drawing');
  // the no-keys sample: 4 drawings read (the image route has no reader), flat-b left out of both numbers: 3 of the
  // 5 drawings left of 6 (drawingTally, IN-131; was "3 / 6" while Simple's tile said 3 / 5, AD-133)
  await expect(page.locator('.adv-stats > div', { hasText: 'Drawings ready' })).toContainText(
    '3 / 5',
  );
  await page.locator('.adv-stats').evaluate((e) => {
    e.scrollIntoView({ block: 'center' });
  });
  await shot(page, testInfo, 'detail-not-a-drawing-extract-stats', offline);
  await picker.evaluate((e) => {
    e.scrollIntoView({ block: 'center' });
  });
  await shot(page, testInfo, 'detail-not-a-drawing-extract', offline);

  // its file page says it in a sentence
  await page
    .getByRole('region', { name: 'Files by stage' })
    .getByRole('link', { name: NOT_A_DRAWING })
    .click();
  await expect(
    page.getByText(
      'The sheet-kind step called this not a drawing: it was read, but it is not counted as a drawing ready.',
    ),
  ).toBeVisible();
  await shot(page, testInfo, 'detail-not-a-drawing-file', offline);
  // the Simple view's tile says the same as Advanced's Extract
  await page.goto(`/#/p/${pid}`);
  await expect(
    page.locator('.ingest-stats dt', { hasText: 'Drawings ready' }).locator('+ dd'),
  ).toHaveText('3 / 5');
  // the Simple view polls on: its project request may still be in the route above when the test ends
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  expect(errors).toEqual([]);
});
