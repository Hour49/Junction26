// The golden demo path (docs/specs/frontend/golden-path.md, steps 1-12 and the conflicts list) on the
// live backend, at the project's viewport, with a screenshot of every screen.
import { readFile } from 'node:fs/promises';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { methodName } from '../src/api/format';
import { filesThrough, noKeys, shot, watchErrors } from './support';

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
    await expect(filesThrough(page)).toHaveText('11 / 11', { timeout: 30_000 });
    await expect(page.getByText('All 8 steps done').first()).toBeVisible();
    await expect(page.locator('dt', { hasText: 'Drawings ready' }).locator('+ dd')).toHaveText(
      '5 / 5',
    );
    const row = (file: string) => page.locator('a[href*="/f/f"]').filter({ hasText: file });
    await expect(row('plans/flat-b.pdf')).toContainText('flagged');
    await expect(row('photos/site.jpg')).toContainText('set aside');
    await expect(row('docs/notes.txt')).toContainText('text only');
    await shot(page, testInfo, '02-project', offline);
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
    await shot(page, testInfo, '04-trace', offline);
  });

  await test.step('GP-31 V5 CF-22: settle the conflicts screen, then back to the rule', async () => {
    await page.getByRole('banner').getByRole('link', { name: 'Conflicts', exact: true }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/conflicts$/);
    await expect(
      page.getByRole('heading', { level: 1, name: /^\d+ conflicts? found$/ }),
    ).toBeVisible();
    const card = page.getByRole('article', { name: 'area of room (name 1.01)' });
    await expect(card).toContainText('plans/flat-b.pdf');
    await expect(card).toContainText('Settled by rule');
    await expect(page.getByText('Needs you')).toHaveCount(0);
    await shot(page, testInfo, '05-conflicts', offline);
    await card.getByRole('button', { name: 'Modify' }).click();
    await card.getByRole('button', { name: /^A\b/ }).click();
    await expect(card).toContainText('Your choice');
    page.once('dialog', (dialog) => void dialog.accept());
    await card.getByRole('button', { name: "Use the rule's value" }).click();
    await expect(card).toContainText('Settled by rule');
  });

  let drawingUrl = '';
  await test.step('GP-32 V6 GP-5: flat-b through its conflict card, as engineer', async () => {
    await page
      .getByRole('article', { name: 'area of room (name 1.01)' })
      .getByRole('link', { name: 'Open in the surveyor workspace' })
      .click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/d\/[0-9a-f]{16}\/surveyor\?q=/);
    await page.getByRole('link', { name: 'Engineer', exact: true }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/d\/[0-9a-f]{16}\/engineer(\?q=.*)?$/);
    drawingUrl = page.url().replace(/\/engineer(\?.*)?$/, '');
    await expect(page.getByText('plans/flat-b.pdf').first()).toBeVisible();
    const image = page.getByRole('img', { name: /Page 1 of plans\/flat-b\.pdf/ }).first();
    await expect(image).toBeVisible();
    await expect
      .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
      .toBeGreaterThan(0);
    // The credit the backend gives this drawing (story #33: every drawing on screen carries its credit).
    const drawingId = /\/d\/([0-9a-f]{16})\//.exec(page.url())?.[1] ?? '';
    const drawing = await page.request.get(`/api/drawings/${drawingId}`);
    const { credit } = (await drawing.json()) as { credit: string | null };
    await expect(
      page.getByText(`Credit: ${credit ?? 'none recorded for this file'}`, { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'How many doors are there?' })).toBeVisible();
    await shot(page, testInfo, '06-engineer', offline);
  });

  await test.step('GP-6 step 5: a count with its marks', async () => {
    await page.getByRole('button', { name: 'How many doors are there?' }).click();
    const doors = turn('How many doors are there?');
    await expect(doors.getByTestId('answer-value')).toHaveText('2');
    await expect(doors).toContainText('One method');
    await expect(doors.getByRole('button', { name: /^Mark \d+: door, counted$/ })).toHaveCount(2);
    // EN-43: the newest turn is scrolled into view
    await expect(doors).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '07-count', offline);
  });

  await test.step('GP-7 step 6: an area where the methods disagree', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill(AREA);
    await page.getByRole('button', { name: 'Ask' }).click();
    const area = turn(AREA);
    await expect(area.getByTestId('answer-value')).toHaveText('30.00 m²');
    await expect(area).toContainText('Methods disagree');
    await expect(area).toContainText(`22.40 m² by ${methodName('polygon_x_scale')}`);
    await expect(area).toContainText(`30.00 m² by ${methodName('printed_label')}`);
    await expect(area.getByRole('button', { name: 'Mark 1: Küche, counted' })).toHaveCount(1);
    // EN-43: the newest turn is scrolled into view
    await expect(area).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '08-area-conflict', offline);
  });

  await test.step('GP-8 step 7: a refusal', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill('What colour is the roof?');
    await page.getByRole('button', { name: 'Ask' }).click();
    const roof = turn('What colour is the roof?');
    await expect(roof).toContainText("I can't answer that from this drawing.");
    await expect(roof).toContainText("This question isn't one I can turn into a count");
    // The refusal code is not shown on the card (QA sign-off, #14).
    await expect(roof).not.toContainText('code:');
    await expect(roof).not.toContainText('unsupported-question');
    await expect(roof.getByRole('button', { name: 'How many doors are there?' })).toBeVisible();
    await expect(roof.getByTestId('answer-value')).toHaveCount(0);
    // EN-43: the newest turn is scrolled into view
    await expect(roof).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '09-refusal', offline);
  });

  await test.step('GP-9, GP-28 step 8: the surveyor queue and the conflicts list', async () => {
    await page.getByRole('link', { name: 'Surveyor', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`^${escape(drawingUrl)}/surveyor(\\?.*)?$`));
    for (const text of [
      'area of room (name 1.01)',
      /area of room \(name küche\)/i,
      '22.40 m² vs 30.00 m²',
      'decided by rule',
    ]) {
      await expect(page.getByText(text).first()).toBeVisible();
    }
    const queue = page.getByRole('table', { name: 'To review' });
    await expect(row(page, 'area of room (name 1.01)', queue)).toContainText('Methods disagree');
    // The room name as printed ('Küche') since #108, lower case before it.
    await expect(row(page, /^area of room \(name küche\)$/i, queue)).toContainText(
      'Methods disagree',
    );
    await shot(page, testInfo, '10-surveyor-queue', offline);
  });

  const kitchen = row(page, 'area of room (name 1.01)');
  await test.step('GP-10 step 9: settle on the drawn outline', async () => {
    await kitchen.getByRole('button', { name: 'area of room (name 1.01)', exact: true }).click();
    await page
      .getByRole('button', { name: `Keep A: 22.40 m² (${methodName('polygon_x_scale')})` })
      .click();
    await expect(kitchen).toContainText('22.40 m²');
    await expect(kitchen).toContainText('Changed in review');
    await expect(page.getByText(/Settled at 22\.40 m²/).first()).toBeVisible();
  });

  await test.step('GP-11 step 10: sign off as Ana', async () => {
    await page.getByRole('textbox', { name: 'Signing as' }).fill('Ana');
    await page.getByRole('button', { name: /^Sign off/ }).click();
    await expect(kitchen).toContainText('Verified');
    await expect(page.getByText(/Signed off by Ana/).first()).toBeVisible();
    await shot(page, testInfo, '11-signed', offline);
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
    await shot(page, testInfo, '12-verified', offline);
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

  await test.step('GP-33 GP-34 V15: the workspace history', async () => {
    await page.getByRole('banner').getByRole('link', { name: 'Workspaces' }).click();
    await expect(page).toHaveURL(/#\/workspaces$/);
    const first = page.locator('button[aria-pressed]').first();
    await expect(first).toContainText('sample-project.zip');
    await expect(first).toHaveAttribute('aria-pressed', 'true');
    const panel = page.getByRole('region', { name: 'Selected workspace' });
    const stat = (label: string) => panel.locator('dt', { hasText: label }).locator('+ dd');
    await expect(stat('Files')).toHaveText('11');
    await expect(stat('Drawings')).toHaveText('5');
    await expect(stat('To review')).toHaveText('1');
    await expect(stat('Signed off')).toHaveText(/^1 of \d+$/);
    const titles = panel.locator('ol li strong');
    await expect(titles.first()).toHaveText('Uploaded sample-project.zip');
    const all = await titles.allTextContents();
    const at = (pattern: RegExp) => all.findIndex((t) => pattern.test(t));
    expect(at(/^Analysis done$/)).toBe(1);
    expect(at(/^Decided by rule: area of room \(name küche\)$/i)).toBeGreaterThan(1);
    expect(at(/^Conflict settled: area of room \(name 1\.01\)$/)).toBeGreaterThan(
      at(/^Decided by rule: area of room \(name küche\)$/i),
    );
    expect(at(/^Signed off: area of room \(name 1\.01\)$/)).toBeGreaterThan(
      at(/^Conflict settled: area of room \(name 1\.01\)$/),
    );
    await expect(panel).toContainText('by Ana');
    // GP-36: no user, no canvas sample data (the drawing credit names the team, so not 'Hour49').
    await expect(page.locator('body')).not.toContainText(/Beatrice|harbour-block-archive/);
    await shot(page, testInfo, '13-workspaces', offline);
  });

  expect(errors, 'GP-19: console or page errors during the path').toEqual([]);
});

test('GP-20: the service is down, then back', async ({ page }) => {
  await page.route('**/api/projects', (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 500, json: { detail: 'internal error', code: 'internal' } })
      : route.fallback(),
  );
  // Home lists no projects any more (IN-53): the list is on #/workspaces, the picker in the header.
  await page.goto('/#/workspaces');
  const main = page.getByRole('main');
  await expect(main.getByText('internal error').first()).toBeVisible();
  await expect(main.getByText(/code: internal/).first()).toBeVisible();
  await page.unroute('**/api/projects');
  await main.getByRole('button', { name: 'Retry' }).click();
  const pickerRetry = page.getByRole('banner').getByRole('button', { name: 'Retry' });
  if (await pickerRetry.isVisible()) await pickerRetry.click();
  await expect(page.getByText('internal error')).toHaveCount(0);
  await expect(main.getByRole('heading', { level: 1, name: 'Your workspaces' })).toBeVisible();
  await expect(
    main.getByText(/workspaces? on this server|No workspaces yet\./).first(),
  ).toBeVisible();
});

/** The table row whose label button is `label` (rows move between the two tables as their state changes). */
function row(page: Page, label: string | RegExp, scope: Page | Locator = page): Locator {
  // `has` is matched inside each row, so it starts from the page.
  return scope
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name: label, exact: true }) });
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
