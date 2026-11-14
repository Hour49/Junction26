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
