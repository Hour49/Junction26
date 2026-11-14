import path from 'node:path';
import { expect, type Page, type TestInfo } from '@playwright/test';

export const OFFLINE = 'Running offline: no API keys, no models';

/** Every console error and uncaught page error of the run (QA.md §2: none allowed on the path). */
export function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

/** `no_keys` of GET /api/info, through the preview's proxy. */
export async function noKeys(page: Page): Promise<boolean> {
  const response = await page.request.get('/api/info');
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { no_keys: boolean }).no_keys;
}

/** Checks the offline text and that nothing scrolls sideways, then saves screenshots/<project>/<name>.png. */
export async function shot(page: Page, testInfo: TestInfo, name: string, offline: boolean) {
  const strip = page.getByText(OFFLINE);
  if (offline) await expect(strip.first()).toBeVisible();
  else await expect(strip).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(
    overflow,
    `${name}: the page scrolls sideways by ${String(overflow)} px`,
  ).toBeLessThanOrEqual(0);
  const dir = path.join(testInfo.config.rootDir, '..', 'screenshots', testInfo.project.name);
  await page.screenshot({ path: path.join(dir, `${name}.png`) });
}

/** The project screen's stats cell "Files through" (ingest.md IN-46: "N / M"). */
export function filesThrough(page: Page) {
  return page.locator('dt', { hasText: 'Files through' }).locator('+ dd');
}

/** Home → "Try the sample project" (fresh=true) → all 11 files through; returns the project id. */
export async function startSample(page: Page): Promise<string> {
  await page.goto('/#/');
  await page.getByRole('button', { name: 'Try the sample project' }).click();
  await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
  await expect(filesThrough(page)).toHaveText('11 / 11', { timeout: 30_000 });
  return /#\/p\/([0-9a-f]{12})$/.exec(page.url())?.[1] ?? '';
}

/** The sample, then a file's page from Documents' file list (parity: no file list on Ingest). */
export async function fileFromDocuments(page: Page, file: string): Promise<string> {
  const pid = await startSample(page);
  await page.goto(`/#/p/${pid}/documents`);
  await page
    .getByRole('region', { name: 'Files' })
    .getByRole('link')
    .filter({ hasText: file })
    .click();
  await expect(page).toHaveURL(/\/f\/f\d+$/);
  return pid;
}

/** The sample's plans/flat-b.pdf on the surveyor route, by its URL (parity: no Surveyor tab; these tests are about
 * the workspace, not the way in, which golden-path.spec.ts walks). */
export async function openSurveyor(page: Page) {
  const pid = await startSample(page);
  const { id } = await drawingOf(page, pid, 'plans/flat-b.pdf');
  await page.goto(`/#/p/${pid}/d/${id}/surveyor`);
  await expect(page).toHaveURL(/\/d\/[0-9a-f]{16}\/surveyor/);
}

/** A drawing of the project by its file: its id and its on-screen name (`drawingLabel`: #224's `name`, else the file
 * name). */
export async function drawingOf(
  page: Page,
  pid: string,
  file: string,
): Promise<{ id: string; label: string }> {
  const project = (await (await page.request.get(`/api/projects/${pid}`)).json()) as {
    drawings: { drawing_id: string; file: string; name?: string | null }[];
  };
  const drawing = project.drawings.find((d) => d.file === file);
  expect(drawing, `${file} is a drawing of ${pid}`).toBeTruthy();
  return {
    id: drawing?.drawing_id ?? '',
    label: drawing?.name || (file.split('/').pop() ?? file),
  };
}

/** The sample through the API (not the ingest screen, whose wording is its own spec's), read to the end. */
export async function sampleDone(page: Page): Promise<string> {
  const started = await page.request.post('/api/projects/sample?fresh=true');
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
