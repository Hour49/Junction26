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
