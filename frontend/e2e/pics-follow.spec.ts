// A plan edit followed onto the floor's services pictures (brief pics-edit-follow W4; backend specs
// services-follow.md § Pictures and discipline-pictures.md AC-20) on the no-keys backend. The upload is
// backend/tests/pics_pair.py's ZIP: a vector plan of the walled flat and the bench renderer's heating and plumbing
// pictures of its floor, plus a heating picture of another floor, named like a sheet set (A-101, H-101, P-101,
// H-102). It needs both settings on: `DISCIPLINE_PICTURES=template SERVICES_FOLLOW=on npx playwright test
// e2e/pics-follow.spec.ts`; with them off (the default run) it skips itself. Screenshots in
// screenshots/<project>/pics-*.png.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

test.skip(
  process.env.DISCIPLINE_PICTURES !== 'template' || process.env.SERVICES_FOLLOW !== 'on',
  'run with DISCIPLINE_PICTURES=template SERVICES_FOLLOW=on',
);

const REMOVE = 'Remove the wall between Bagno 1.01 and Stanza 1.02';

/** The plan + pictures ZIP, made by the backend's test helper (rendered from a small IFC, a few seconds). */
function pairZip(e2eDir: string): Buffer {
  const backend = path.join(e2eDir, '..', '..', 'backend');
  const code =
    "import sys; sys.path.insert(0, 'tests'); from pics_pair import pair_zip; sys.stdout.buffer.write(pair_zip())";
  return execFileSync('uv', ['run', '--locked', 'python', '-c', code], { cwd: backend });
}

/** Uploads the ZIP, waits until ingest is done, opens the chat and asks for the wall to go: the edit card. */
async function removed(page: Page, e2eDir: string) {
  const started = await page.request.post('/api/projects?name=pics-pair.zip', {
    data: pairZip(e2eDir),
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(started.status()).toBe(202);
  const { id } = (await started.json()) as { id: string };
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/projects/${id}`)).json()) as { state: string }).state,
      { timeout: 60_000 },
    )
    .toBe('done');
  await page.goto(`/#/p/${id}/chat`);
  await expect(page.getByRole('button', { name: 'Draw on the plan' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Question' }).fill(REMOVE);
  await page.getByRole('button', { name: 'Ask' }).click();
  const card = page.getByRole('article', { name: REMOVE }).last().locator('.ag-card--edit');
  await expect(card).toBeVisible({ timeout: 30_000 });
  return card;
}

test('W4-1: with no keys, the heating and plumbing pictures are read and followed (each tab has a lane)', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await removed(page, testInfo.config.rootDir);
  const tabs = card.getByRole('group', { name: 'Discipline' });
  // read from the pictures (AC-20: by their file names), so neither lane says "no model"
  for (const name of ['Heating', 'Plumbing']) {
    const tab = tabs.getByRole('button', { name: new RegExp(`^${name}`) });
    await expect(tab).toBeVisible({ timeout: 30_000 });
    await expect(tab).not.toContainText('no model');
  }
  await expect(tabs.getByRole('button', { name: /^Ventilation/ })).toContainText('no model');
  await tabs.getByRole('button', { name: /^Heating/ }).click();
  await expect(card.getByRole('region', { name: 'Heating after the change' })).toBeVisible();
  await shot(page, testInfo, 'pics-heating', offline);
  expect(errors).toEqual([]);
});

// shortcut: fixme until W1 (pairing, pics/pairing), W2 (the picture in the follow, pics/follow-picture) and W3 (the
// picture in the tab, pics/edit-picture-tabs) are on main; then drop the fixme and fit the locators to W3's DOM.
test.fixme('W4-2: the heating tab shows the H-101 picture with the wall struck out and why it is that floor', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await removed(page, testInfo.config.rootDir);
  await card
    .getByRole('group', { name: 'Discipline' })
    .getByRole('button', { name: /^Heating/ })
    .click();
  const panel = card.getByRole('region', { name: 'Heating after the change' });
  // the same floor by its names (H-101 / A-101, floor 1), never the floor 2 sheet (H-102)
  await expect(panel).toContainText(/floor 1|101/i);
  await expect(panel).not.toContainText('H-102');
  // the picture itself, with the removed wall's strip drawn on it, and a way to refuse the pairing
  await expect(card.getByRole('img', { name: /H-101/ })).toBeVisible();
  await expect(card.getByRole('button', { name: 'Not this sheet' })).toBeVisible();
  // two radiators on the wall to move, the supply pipe through it (services-follow.md SFP-1)
  await expect(panel.locator('.ms-action')).not.toHaveCount(0);
  await shot(page, testInfo, 'pics-heating-picture', offline);
  expect(errors).toEqual([]);
});
