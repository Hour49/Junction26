// QA round 1 layout bugs (board #14), as browser tests on the live no-keys backend. Each fails while its bug is there.
import { expect, test } from '@playwright/test';
import { filesThrough, noKeys, openSurveyor, shot, startSample } from './support';

// No hyphens or spaces: nothing the browser may break the line at.
const LONG_NAME = 'Hafenstrasse_12_Bauabschnitt_B_Ausfuehrungsplaene_Rev07a.txt';

test('R1-5-4 / R1-4-1: a long project name does not widen the page at 390x844', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'a phone-width bug');
  expect(LONG_NAME).toHaveLength(60);
  const upload = await page.request.post(`/api/projects?name=${encodeURIComponent(LONG_NAME)}`, {
    data: Buffer.from('notes from the site office\n'),
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  expect(upload.status()).toBe(202);
  const { id } = (await upload.json()) as { id: string };
  const sample = await startSample(page);

  for (const project of [id, sample]) {
    await page.goto(`/#/p/${project}`);
    await expect(filesThrough(page)).toHaveText(/^\d+ \/ \d+$/);
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width, `#/p/${project}: page width at a 390 px viewport`).toBeLessThanOrEqual(390);
  }
});

test('R1-4-2: the takeoff shows at least 10 whole rows at 1440x900', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'a desktop-width bug');
  await openSurveyor(page);
  await expect(page.getByRole('table', { name: 'To review' })).toBeVisible();
  // For each row's label button: is it wholly on screen, and wholly inside its nearest clipping box?
  const rows = await page.evaluate(() => {
    const clipBox = (element: Element) => {
      for (let at = element.parentElement; at; at = at.parentElement) {
        const style = getComputedStyle(at);
        if (/(auto|scroll|hidden|clip)/.test(style.overflowX + style.overflowY)) {
          return at.getBoundingClientRect();
        }
      }
      return null;
    };
    return [...document.querySelectorAll('tr th[scope="row"] button')].map((button) => {
      const box = button.getBoundingClientRect();
      const clip = clipBox(button);
      const inClip =
        !clip ||
        (box.left >= clip.left - 0.5 &&
          box.right <= clip.right + 0.5 &&
          box.top >= clip.top - 0.5 &&
          box.bottom <= clip.bottom + 0.5);
      const onScreen = box.top >= 0 && box.bottom <= window.innerHeight && box.width > 0;
      return {
        label: button.textContent,
        onScreen,
        inClip,
        cutSideways: !!clip && (box.left < clip.left - 0.5 || box.right > clip.right + 0.5),
      };
    });
  });
  const whole = rows.filter((row) => row.onScreen && row.inClip);
  expect(whole.length, 'rows wholly visible without scrolling').toBeGreaterThanOrEqual(10);
  expect(
    rows.filter((row) => row.cutSideways).map((row) => row.label),
    'row buttons cut at the side of their box',
  ).toEqual([]);
});

test('R1 engineer: an IFC answer fits 390x844', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'a phone-width check');
  await startSample(page);
  await page.locator('a[href*="/f/f"]').filter({ hasText: 'model/house.ifc' }).click();
  await page.getByRole('link', { name: 'Open the drawing' }).click();
  await expect(page).toHaveURL(/\/d\/[0-9a-f]{16}\/engineer$/);
  const drawingId = /\/d\/([0-9a-f]{16})\//.exec(page.url())?.[1] ?? '';
  const drawing = await page.request.get(`/api/drawings/${drawingId}`);
  const { suggestions } = (await drawing.json()) as { suggestions: { question: string }[] };
  const question = suggestions[0]?.question ?? '';
  expect(question, 'the IFC drawing has a suggested question').not.toBe('');
  await page.getByRole('button', { name: question, exact: true }).first().click();
  const turn = page.getByRole('article', { name: question }).last();
  await expect(turn.getByTestId('answer-value')).toBeVisible();
  await expect(turn).toBeInViewport({ ratio: 0.2 });
  await shot(page, testInfo, 'qa-r1-ifc-390', await noKeys(page));
});
