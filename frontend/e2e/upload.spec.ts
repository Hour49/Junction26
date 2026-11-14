// IN-89 (Bogdan 2026-11-15): a ZIP picked on the home screen is sent, the server says it received it, and the app
// opens its extraction without a click; the extraction view says what was received and the files the server found.
// The sending state itself is covered by HomeScreen.test.tsx (locally the bytes go out at once).
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { noKeys, shot, watchErrors } from './support';

/** A ZIP of two of the sample's files, made by the backend's own script (as start-backend.sh runs uv); not the
 * sample archive itself, whose ingest the golden path expects to own on the shared backend. */
function siteZip(e2eDir: string): Buffer {
  const backend = path.join(e2eDir, '..', '..', 'backend');
  const code =
    'import sys; from scripts.make_sample_archive import build_archive, text_pdf, raster_plan, png_bytes; ' +
    "sys.stdout.buffer.write(build_archive({'notes.pdf': text_pdf(), 'plan.png': png_bytes(raster_plan())}))";
  return execFileSync('uv', ['run', '--locked', 'python', '-c', code], { cwd: backend });
}

test('IN-89: a ZIP upload is received by the server, then its extraction opens by itself', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const zip = siteZip(testInfo.config.rootDir);
  await page.goto('/#/');
  await page.locator('input[type=file]').setInputFiles({
    name: 'site.zip',
    mimeType: 'application/zip',
    buffer: zip,
  });
  await expect(page).toHaveURL(/#\/p\/[0-9a-f]+$/);
  const received = page.getByRole('status', { name: 'Upload received' });
  const kb = Math.max(1, Math.round(zip.length / 1024)); // the ZIP is under 1 MB (sizeText)
  expect(zip.length).toBeLessThan(2 ** 20);
  await expect(received).toContainText(
    `Uploaded: site.zip, ${String(kb)} KB, received by the server.`,
  );
  await expect(received).toHaveText(/ \d+ files? found\.$/, { timeout: 30_000 });
  await expect(page.getByRole('region', { name: 'Progress' })).toBeVisible();
  await shot(page, testInfo, 'upload-received', offline);
  expect(errors).toEqual([]);
});
