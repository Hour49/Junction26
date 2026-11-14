// The 3D view on the file page (docs/specs/frontend/model-3d.md M3-19): a synthetic IFC (licence-safe, fixtures/README.md)
// uploaded as its own project, opened from Documents, converted on the first GET (MODEL_3D=1 in start-backend.sh).
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

const FILE = 'model-3d-house.ifc';

test('M3-19 Documents -> the IFC file -> Show in 3D draws the model, the controls work', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
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
  // the browser logs the expected 409 of "Preparing the 3D view…" as a failed resource; nothing else allowed
  expect(errors.filter((e) => !e.includes('status of 409'))).toEqual([]);
});
