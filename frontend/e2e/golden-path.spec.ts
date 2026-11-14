// The golden demo path (docs/specs/frontend/golden-path.md, steps 1-12 and the conflicts list) on the
// live backend, at the project's viewport, with a screenshot of every screen.
import { readFile } from 'node:fs/promises';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

const AREA = 'What is the net floor area of room 1.01?';

test('GP-1..GP-13, GP-28: the golden demo path', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const turn = (question: string) => page.getByRole('article', { name: question }).last();

  await test.step('GP-2 step 1: home', async () => {
    await page.goto('/#/');
    await expect(page.getByRole('button', { name: 'Try the sample project' })).toBeVisible();
    await shot(page, testInfo, '01-home', offline);
  });

  await test.step('GP-3 step 2: the sample project ingests', async () => {
    await page.getByRole('button', { name: 'Try the sample project' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
    await expect(page.getByText('11 of 11 files finished').first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText('Done', { exact: true }).first()).toBeVisible();
    const row = (file: string) => page.locator('a[href*="/f/f"]').filter({ hasText: file });
    await expect(row('plans/flat-b.pdf')).toContainText('flagged');
    await expect(row('photos/site.jpg')).toContainText('set aside');
    await expect(row('docs/notes.txt')).toContainText('text only');
    await shot(page, testInfo, '02-ingest-done', offline);
  });

  await test.step('GP-4 step 3: the trace of plans/flat-b.pdf', async () => {
    await page.locator('a[href*="/f/f"]').filter({ hasText: 'plans/flat-b.pdf' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/f\/f\d+$/);
    await expect(page.getByText('flagged').first()).toBeVisible();
    await expect(page.getByText('1 conflict(s) between the two methods').first()).toBeVisible();
    await expect(
      page.getByText('5 quantities measured twice, 1 conflict(s)').first(),
    ).toBeVisible();
    // the write stage's `did`
    await expect(page.getByText(/drawing model [0-9a-f]{16} stored/).first()).toBeVisible();
    await shot(page, testInfo, '03-trace', offline);
  });

  let drawingUrl = '';
  await test.step('GP-5 step 4: the drawing as engineer', async () => {
    await page.getByRole('link', { name: 'Open the drawing' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/d\/[0-9a-f]{16}\/engineer$/);
    drawingUrl = page.url().replace(/\/engineer$/, '');
    await expect(page.getByText('plans/flat-b.pdf').first()).toBeVisible();
    const image = page.getByRole('img', { name: /Page 1 of plans\/flat-b\.pdf/ }).first();
    await expect(image).toBeVisible();
    await expect
      .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
      .toBeGreaterThan(0);
    await expect(page.getByText('Credit: none recorded for this file').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'How many doors are there?' })).toBeVisible();
    await shot(page, testInfo, '04-engineer', offline);
  });

  await test.step('GP-6 step 5: a count with its marks', async () => {
    await page.getByRole('button', { name: 'How many doors are there?' }).click();
    const doors = turn('How many doors are there?');
    await expect(doors.getByTestId('answer-value')).toHaveText('2');
    await expect(doors).toContainText('One method');
    await expect(doors.getByRole('button', { name: /^Mark \d+: door, counted$/ })).toHaveCount(2);
    // EN-43: the newest turn is scrolled into view
    await expect(doors).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '05-count', offline);
  });

  await test.step('GP-7 step 6: an area where the methods disagree', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill(AREA);
    await page.getByRole('button', { name: 'Ask' }).click();
    const area = turn(AREA);
    await expect(area.getByTestId('answer-value')).toHaveText('30.00 m²');
    await expect(area).toContainText('Methods disagree');
    await expect(area).toContainText('22.40 m² by polygon_x_scale');
    await expect(area).toContainText('30.00 m² by printed_label');
    await expect(area.getByRole('button', { name: 'Mark 1: Küche, counted' })).toHaveCount(1);
    // EN-43: the newest turn is scrolled into view
    await expect(area).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '06-area-conflict', offline);
  });

  await test.step('GP-8 step 7: a refusal', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill('What colour is the roof?');
    await page.getByRole('button', { name: 'Ask' }).click();
    const roof = turn('What colour is the roof?');
    await expect(roof).toContainText("I can't answer that from this drawing.");
    await expect(roof).toContainText('unsupported-question');
    await expect(roof.getByRole('button', { name: 'How many doors are there?' })).toBeVisible();
    await expect(roof.getByTestId('answer-value')).toHaveCount(0);
    // EN-43: the newest turn is scrolled into view
    await expect(roof).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '07-refusal', offline);
  });

  await test.step('GP-9, GP-28 step 8: the surveyor queue and the conflicts list', async () => {
    await page.getByRole('link', { name: 'Surveyor', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`^${escape(drawingUrl)}/surveyor(\\?.*)?$`));
    for (const text of [
      'area of room (name 1.01)',
      'area of room (name küche)',
      '22.40 m² vs 30.00 m²',
      'decided by rule',
    ]) {
      await expect(page.getByText(text).first()).toBeVisible();
    }
    const queue = page.getByRole('table', { name: 'To review' });
    await expect(row(page, 'area of room (name 1.01)', queue)).toContainText('Methods disagree');
    await expect(row(page, 'area of room (name küche)', queue)).toContainText('Methods disagree');
    await shot(page, testInfo, '08-surveyor-queue', offline);
  });

  const kitchen = row(page, 'area of room (name 1.01)');
  await test.step('GP-10 step 9: settle on the drawn outline', async () => {
    await kitchen.getByRole('button', { name: 'area of room (name 1.01)', exact: true }).click();
    await page.getByRole('button', { name: 'Keep A: 22.40 m² (polygon_x_scale)' }).click();
    await expect(kitchen).toContainText('22.40 m²');
    await expect(kitchen).toContainText('Changed in review');
    await expect(page.getByText(/Settled at 22\.40 m²/).first()).toBeVisible();
  });

  await test.step('GP-11 step 10: sign off as Ana', async () => {
    await page.getByRole('textbox', { name: 'Signing as' }).fill('Ana');
    await page.getByRole('button', { name: /^Sign off/ }).click();
    await expect(kitchen).toContainText('Verified');
    await expect(page.getByText(/Signed off by Ana/).first()).toBeVisible();
    await shot(page, testInfo, '09-signed', offline);
  });

  await test.step('GP-12 step 11: the engineer sees it verified', async () => {
    await page.getByRole('link', { name: 'Engineer', exact: true }).click();
    await page.getByRole('textbox', { name: 'Question' }).fill(AREA);
    await page.getByRole('button', { name: 'Ask' }).click();
    const verified = turn(AREA);
    await expect(verified.getByTestId('answer-value')).toHaveText('22.40 m²');
    await expect(verified).toContainText('Verified');
    await expect(verified).toContainText(/Verified by Ana, \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/);
    await expect(verified).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '10-verified', offline);
  });

  await test.step('GP-13 step 12: export the takeoff as CSV', async () => {
    await page.getByRole('link', { name: 'Surveyor', exact: true }).click();
    const download = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Export CSV' }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe('flat-b-takeoff.csv');
    const csv = await readFile(await file.path(), 'utf8');
    const line = csv.split('\n').find((l) => l.startsWith('plans/flat-b.pdf,area:room|name=1.01,'));
    expect(line).toMatch(/,22\.401,m2,signed,30\.0,/);
    expect(line).toMatch(/,Ana,/);
  });

  expect(errors, 'GP-19: console or page errors during the path').toEqual([]);
});

test('GP-20: the service is down, then back', async ({ page }) => {
  await page.route('**/api/projects', (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 500, json: { detail: 'internal error', code: 'internal' } })
      : route.fallback(),
  );
  await page.goto('/#/');
  await expect(page.getByText('internal error').first()).toBeVisible();
  await expect(page.getByText(/internal\)|code: internal/).first()).toBeVisible();
  const retries = page.getByRole('button', { name: 'Retry' });
  await expect(retries.first()).toBeVisible();
  await page.unroute('**/api/projects');
  // The project list (in main) and the shell's project picker (in the header) each show the error with a Retry.
  await page.getByRole('main').getByRole('button', { name: 'Retry' }).click();
  const pickerRetry = page.getByRole('banner').getByRole('button', { name: 'Retry' });
  if (await pickerRetry.isVisible()) await pickerRetry.click();
  await expect(page.getByText('internal error')).toHaveCount(0);
  await expect(page.getByText(/sample-project\.zip|No projects yet/).first()).toBeVisible();
});

/** The table row whose label button is `label` (rows move between the two tables as their state changes). */
function row(page: Page, label: string, scope: Page | Locator = page): Locator {
  // `has` is matched inside each row, so it starts from the page.
  return scope
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name: label, exact: true }) });
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
