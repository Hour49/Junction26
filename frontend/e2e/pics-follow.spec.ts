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

test('W4-2: the heating tab shows the H-101 picture with the edit, why it is that floor, and can refuse it', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const card = await removed(page, testInfo.config.rootDir);
  const tabs = card.getByRole('group', { name: 'Discipline' });
  const heating = tabs.getByRole('button', { name: /^Heating/ });
  await expect(heating).not.toContainText(/no model|not aligned/, { timeout: 30_000 });
  await heating.click();
  // AC-42: paired by the sheets' names (the same floor and sheet number on both), never the floor 2 sheet (H-102)
  const line = card.locator('.ms-pairing');
  await expect(line).toContainText("Paired by the sheets' names");
  await expect(line).toContainText("'Floor 1' on both");
  await expect(line).toContainText('H-101');
  await expect(line).not.toContainText('H-102');
  // AC-40, AC-41: the heating sheet itself, the edit drawn on it; Before shows it as drawn
  const picture = card.getByRole('img', {
    name: /H-101 Floor 1 heating\.png, page 1, with the proposed change/,
  });
  await expect(picture).toBeVisible();
  await expect(
    card.getByRole('region', { name: 'Heating after the change' }).locator('.ms-action'),
  ).not.toHaveCount(0);
  await shot(page, testInfo, 'pics-heating-picture', offline);
  await card.getByRole('button', { name: 'Before' }).click();
  await expect(
    card.getByRole('img', { name: /H-101 Floor 1 heating\.png, page 1, as drawn/ }),
  ).toBeVisible();
  await card.getByRole('button', { name: 'After' }).click();
  // plumbing: its own sheet of the floor
  await tabs.getByRole('button', { name: /^Plumbing/ }).click();
  await expect(card.locator('.ms-pairing')).toContainText('P-101');
  await expect(
    card.getByRole('img', { name: /P-101 Floor 1 plumbing\.png, page 1/ }),
  ).toBeVisible();
  // AC-43: a wrong pairing can be refused, and the tab then says it is not checked
  await tabs.getByRole('button', { name: /^Heating/ }).click();
  await card.getByRole('button', { name: 'Not this sheet' }).click();
  await expect(card).toContainText("Not checked: you said this is not this floor's heating sheet.");
  await expect(tabs.getByRole('button', { name: /^Heating/ })).toContainText('not checked');
  await expect(card.getByRole('button', { name: 'Use this sheet again' })).toBeVisible();
  // AC-44: no horizontal scroll at either width
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
