// The agent chat (docs/specs/agent-chat.md §1 and §4) on the no-keys backend, whose chat model is the rules planner
// (CHAT_MODEL=rules): an answer turn with its steps line, then a wall removed on a synthetic swiss sheet with grey
// wall fills (backend/tests/swiss_walls.py) and accepted. Screenshots in screenshots/<project>/agent-*.png.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const STEPS = /^\d+ steps? · \d+\.\d s · /;

/** ag-geom's walled sheet as PDF bytes, made by the backend's test helper (as start-backend.sh runs uv). */
function walledFlat(e2eDir: string): Buffer {
  const backend = path.join(e2eDir, '..', '..', 'backend');
  const code =
    "import sys; sys.path.insert(0, 'tests'); from swiss_walls import walled_flat; " +
    'sys.stdout.buffer.write(walled_flat())';
  return execFileSync('uv', ['run', '--locked', 'python', '-c', code], { cwd: backend });
}

/** Uploads one file as a project and waits until it is read; returns the project id. */
async function uploaded(page: Page, name: string, body: Buffer): Promise<string> {
  const started = await page.request.post(`/api/projects?name=${encodeURIComponent(name)}`, {
    data: body,
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(started.status()).toBe(202);
  const { id } = (await started.json()) as { id: string };
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/projects/${id}`)).json()) as { state: string }).state,
      { timeout: 30_000 },
    )
    .toBe('done');
  return id;
}

async function ask(page: Page, message: string) {
  // A cold load shows the ask chat until /api/info answers (chat.md CH-43): type into the agent chat.
  await expect(page.getByRole('button', { name: 'Point at the plan' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Question' }).fill(message);
  await page.getByRole('button', { name: 'Ask' }).click();
  return page.getByRole('article', { name: message }).last();
}

test('AC-39: the empty chat says what was read, and the ask box stays above the fold', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const id = await sampleDone(page);
  await page.goto(`/#/p/${id}/chat`);
  await expect(page.getByRole('button', { name: 'Point at the plan' })).toBeVisible();
  const read = page.getByRole('region', { name: 'What I read' });
  await expect(read).toBeVisible();
  // the first screen is where a judge types: its ask box is fully in view, the block notwithstanding (keycheck 334)
  const box = await page.getByRole('textbox', { name: 'Question' }).boundingBox();
  const viewport = page.viewportSize();
  expect(box && viewport).toBeTruthy();
  if (box && viewport) expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
  await shot(page, testInfo, 'agent-empty', offline);
  expect(errors).toEqual([]);
});

test('AC-30 AC-31: a question gets an answer card with its steps line', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const id = await sampleDone(page);
  await page.goto(`/#/p/${id}/chat`);
  const turn = await ask(page, 'How many doors are there?');
  const card = turn.locator('.ag-card');
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toHaveClass(/ag-card--(answer|dont_know)/);
  const steps = card.locator('.ag-steps summary');
  await expect(steps).toHaveText(STEPS);
  await steps.click();
  await expect(card.locator('.ag-steps li').first()).toBeVisible();
  await shot(page, testInfo, 'agent-answer', offline);
  expect(errors).toEqual([]);
});

test('AC-32 AC-35: removing the wall between two rooms gives an edit card that can be accepted', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const id = await uploaded(page, 'walled-flat.pdf', walledFlat(testInfo.config.rootDir));
  await page.goto(`/#/p/${id}/chat`);
  const turn = await ask(page, 'Remove the wall between Bagno 1.01 and Stanza 1.02');
  const card = turn.locator('.ag-card--edit');
  await expect(card).toBeVisible({ timeout: 30_000 });
  const plan = card.getByRole('figure', { name: 'Proposed plan' });
  await expect(plan.locator('.ag-overlay .ag-removed').first()).toBeAttached();
  await expect(plan.getByText('Demolished (yellow, dashed)')).toBeVisible();
  await expect(card.locator('.ag-changes li').first()).toContainText('Removed');
  await expect(card.locator('.ag-changes')).toContainText('→');
  await expect(card.locator('.ag-steps summary')).toHaveText(STEPS);
  await shot(page, testInfo, 'agent-edit', offline);

  const before = card.getByRole('button', { name: 'Before' });
  await before.click();
  await expect(before).toHaveAttribute('aria-pressed', 'true');
  await expect(plan.locator('.ag-overlay')).toHaveCount(0);
  await card.getByRole('button', { name: 'After' }).click();
  await expect(plan.locator('.ag-overlay')).toHaveCount(1);

  await card.getByRole('button', { name: 'Accept' }).click();
  await expect(card.getByRole('status')).toHaveText('Accepted');
  await expect(card.getByRole('button', { name: 'Reject' })).toHaveCount(0);
  await shot(page, testInfo, 'agent-accepted', offline);
  expect(errors).toEqual([]);
});

// The walled sheet (backend/tests/swiss_walls.py) in page fractions of its 600 × 400 pt page: Stanza 1.02 spans
// x 0.314..0.498, y 0.25..0.463 (3.89 × 3 m, 11.66 m²). This box (about 1.1 × 2.5 m) leaves it about 9 m²: under
// Zürich's 10 m², over Finland's 7 m² (spec plan-edit-law-check §1 steps 2 and 4).
const STORAGE_BOX = { x0: 0.44, y0: 0.27, x1: 0.49, y1: 0.45 };

/** Walled sheet, `?pack=` as given, a box over most of Stanza 1.02, "Put a storage room here": the edit card. */
async function storageEdit(page: Page, e2eDir: string, pack: string | null) {
  const id = await uploaded(page, 'walled-flat.pdf', walledFlat(e2eDir));
  await page.goto(`/#/p/${id}/chat${pack ? `?pack=${pack}` : ''}`);
  await page.getByRole('button', { name: 'Point at the plan' }).click();
  const frame = page.getByRole('region', { name: 'Point at the plan' }).locator('.vw-frame');
  const img = frame.locator('img');
  await expect
    .poll(() => img.evaluate((el) => (el as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
  // page.mouse is in viewport coordinates: the frame must be on screen, and still, before the drag.
  await frame.scrollIntoViewIfNeeded();
  let r = await frame.boundingBox();
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(100);
    const now = await frame.boundingBox();
    if (now && r && JSON.stringify(now) === JSON.stringify(r)) break;
    r = now;
  }
  if (!r) throw new Error('no page frame');
  // A mouse drag on every project (a moving touch pans the viewer).
  await page.mouse.move(r.x + STORAGE_BOX.x0 * r.width, r.y + STORAGE_BOX.y0 * r.height);
  await page.mouse.down();
  await page.mouse.move(r.x + STORAGE_BOX.x1 * r.width, r.y + STORAGE_BOX.y1 * r.height, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(page.getByRole('button', { name: /^Remove Area on .+, page 1$/ })).toBeVisible();
  const turn = await ask(page, 'Put a storage room here');
  const card = turn.locator('.ag-card--edit');
  await expect(card).toBeVisible({ timeout: 30_000 });
  return card;
}

test('LC-11 LC-12: a storage room boxed into Stanza 1.02 under Zürich rules shows "Would not meet"', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await storageEdit(page, testInfo.config.rootDir, 'ch-zh');
  const law = card.getByRole('region', { name: /^Building rules · / });
  await expect(law).toContainText('Canton of Zürich');
  const fail = law
    .getByRole('listitem')
    .filter({ has: page.locator('.ag-law-status', { hasText: 'Would not meet' }) })
    .first();
  await expect(fail).toContainText('Stanza 1.02');
  await expect(fail.getByRole('link').first()).toHaveAttribute('target', '_blank');
  await expect(law).toContainText('not a permit check');
  await fail.getByRole('button', { name: 'Stanza 1.02' }).click();
  await expect(card.locator('.ag-hot')).toHaveCount(1);
  await shot(page, testInfo, 'agent-law-ch-zh', offline);
  expect(errors).toEqual([]);
});

test('LC-11 LC-12: the same box under Finnish rules does not break the room-area rule', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await storageEdit(page, testInfo.config.rootDir, 'fi');
  const law = card.getByRole('region', { name: /^Building rules · / });
  await expect(law).toContainText('Finland');
  // The status label, not the row: a row's explanation may say "would not meet today's rule" in words.
  await expect(law.locator('.ag-law-status', { hasText: 'Would not meet' })).toHaveCount(0);
  const area = law.getByRole('listitem').filter({ hasText: 'at least 7 m²' });
  await expect(area).toContainText('✓ Meets');
  await expect(area).toContainText('Stanza 1.02');
  await expect(law).toContainText('not a permit check');
  await shot(page, testInfo, 'agent-law-fi', offline);
  expect(errors).toEqual([]);
});

test('LC-14: with no country the edit card asks to pick one and says nothing about law', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await storageEdit(page, testInfo.config.rootDir, null);
  const law = card.getByRole('region', { name: 'Building rules' });
  await expect(law).toContainText('Pick a country to check this change against its building rules');
  await expect(law.getByRole('listitem')).toHaveCount(0);
  await law.getByRole('button', { name: 'Pick a country' }).click();
  await expect(page.getByRole('group', { name: 'Building rules the agent follows' })).toBeVisible();
  await shot(page, testInfo, 'agent-law-nopack', offline);
  expect(errors).toEqual([]);
});
