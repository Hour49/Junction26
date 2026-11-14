// The 3D view (docs/specs/frontend/model-3d.md): a synthetic IFC (licence-safe, fixtures/README.md) uploaded as its
// own project, converted on the first GET (MODEL_3D=1 in start-backend.sh). M3-19 the file page, M3-17 the chat.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

const FILE = 'model-3d-house.ifc';

/** The fixture IFC uploaded as its own project, read to the end; returns the project id. */
async function uploaded(page: Page, testInfo: TestInfo): Promise<string> {
  const body = readFileSync(path.join(testInfo.config.rootDir, 'fixtures', FILE));
  const started = await page.request.post(`/api/projects?name=${encodeURIComponent(FILE)}`, {
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

/** Console errors but the expected 409 of "Preparing the 3D view…", which the browser logs as a failed resource. */
const unexpected = (errors: string[]) => errors.filter((e) => !e.includes('status of 409'));

test('M3-19 Documents -> the IFC file -> Show in 3D draws the model, the controls work', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const id = await uploaded(page, testInfo);
  await page.goto(`/#/p/${id}/documents`);
  await page
    .getByRole('region', { name: 'Files' })
    .getByRole('link')
    .filter({ hasText: FILE })
    .click();
  const card = page.getByRole('region', { name: '3D view' });
  await card.getByRole('button', { name: 'Show in 3D' }).click();
  // The first GET starts the conversion (409, "Preparing the 3D view…", retried every 5 s): bounded wait.
  const reset = card.getByRole('button', { name: 'Reset view' });
  await expect(reset).toBeVisible({ timeout: 60_000 });

  const canvas = card.getByRole('img', { name: `3D view of ${FILE}` });
  await canvas.scrollIntoViewIfNeeded();
  // The toolbar sits over the canvas; its hover state is not the picture: masked.
  const picture = () => canvas.screenshot({ mask: [card.getByRole('toolbar')] });
  const first = await picture();
  await card.getByRole('button', { name: 'Zoom in' }).click();
  await card.getByRole('button', { name: 'Rotate left' }).click();
  // Something is drawn: moving the camera changes the picture (a blank canvas would not change).
  expect((await picture()).equals(first)).toBe(false);
  await reset.click();
  await expect.poll(async () => (await picture()).equals(first)).toBe(true);

  for (const name of ['Rotate left', 'Rotate right', 'Zoom in', 'Zoom out', 'Reset view']) {
    const box = await card.getByRole('button', { name }).boundingBox();
    expect(box?.width, name).toBeGreaterThanOrEqual(44);
    expect(box?.height, name).toBeGreaterThanOrEqual(44);
  }
  await shot(page, testInfo, 'model3d-file', await noKeys(page));
  expect(unexpected(errors)).toEqual([]);
});

test("M3-17 the chat answer's References open the 3D view with the counted door highlighted", async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const id = await uploaded(page, testInfo);
  await page.goto(`/#/p/${id}/chat?ask=${encodeURIComponent('How many doors are there?')}`);
  // the 3D button sits in the answer figure's header, beside the drawing's name
  const open = page
    .getByRole('figure', { name: /^Reference \d+ of \d+$/ })
    .getByRole('button', { name: /^View in 3D: / });
  await expect(open).toBeVisible({ timeout: 30_000 });
  expect((await open.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  await open.click();
  const dialog = page.getByRole('dialog', { name: /^3D view: / });
  await expect(dialog.getByRole('button', { name: 'Reset view' })).toBeVisible({ timeout: 60_000 });
  // part 3: the door in words (colour is never the only cue), the rest dimmed
  await expect(dialog.getByRole('list', { name: 'Highlighted elements' })).toHaveText(
    'Affected: 1',
  );
  await shot(page, testInfo, 'model3d-chat', await noKeys(page));
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(open).toBeFocused();
  expect(unexpected(errors)).toEqual([]);
});

test("M3-22 the agent chat's plan pane opens the model with the newest answer's walls highlighted", async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const id = await uploaded(page, testInfo);
  await page.goto(`/#/p/${id}/chat?ask=${encodeURIComponent('How many walls are there?')}`);
  // ui-bugs 5: one round "3D" button in the answer figure's header (no longer in References).
  await expect(
    page
      .getByRole('figure', { name: /^Reference / })
      .getByRole('button', { name: /^View in 3D: / }),
  ).toBeVisible({ timeout: 30_000 });
  // Beside the chat at 1440; a sheet over it on a phone, opened by "Show the plan".
  if (testInfo.project.name === 'phone')
    await page.getByRole('button', { name: 'Show the plan' }).click();
  const pane = page.getByRole('complementary', { name: 'Plan' });
  const open = pane.getByRole('button', { name: /^View in 3D: / });
  expect((await open.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  await open.click();
  const dialog = page.getByRole('dialog', { name: /^3D view: / });
  await expect(dialog.getByRole('button', { name: 'Reset view' })).toBeVisible({ timeout: 60_000 });
  await expect(dialog.getByRole('list', { name: 'Highlighted elements' })).toHaveText(
    'Affected: 4',
  );
  await shot(page, testInfo, 'model3d-pane', await noKeys(page));
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(pane).toBeVisible(); // Esc closed the dialog only, not the plan sheet behind it
  await expect(open).toBeFocused();
  expect(unexpected(errors)).toEqual([]);
});
