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

/** Home → "Try the sample project" (fresh=true) → all 11 files finished; returns the project id. */
export async function startSample(page: Page): Promise<string> {
  await page.goto('/#/');
  await page.getByRole('button', { name: 'Try the sample project' }).click();
  await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
  await expect(page.getByText('11 of 11 files finished').first()).toBeVisible({ timeout: 30_000 });
  return /#\/p\/([0-9a-f]{12})$/.exec(page.url())?.[1] ?? '';
}

/** The sample's plans/flat-b.pdf on the surveyor route (via its trace and the engineer page). */
export async function openSurveyor(page: Page) {
  await startSample(page);
  await page.locator('a[href*="/f/f"]').filter({ hasText: 'plans/flat-b.pdf' }).click();
  await page.getByRole('link', { name: 'Open the drawing' }).click();
  await page.getByRole('link', { name: 'Surveyor', exact: true }).click();
  await expect(page).toHaveURL(/\/d\/[0-9a-f]{16}\/surveyor/);
}
